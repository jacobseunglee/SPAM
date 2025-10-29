"""VM Snapshot Management for SPAM"""

from typing import Optional
from cli import CLI
import arguments.options as options
import utils.utils as utils
import conf.config as config
from utils.exceptions import ValidationError, SnapshotError
from utils.validation import validate_vmid, validate_node_name, validate_snapshot_name


class Snapshot(CLI):
    name = "snapshot"
    
    def __init__(self, args):
        super().__init__(args)
        self.snapshot_args: dict = {}
        self.environment: Optional[config.Env] = None

    def init_parser(self, usage: str = "", desc: Optional[str] = None) -> None:
        super().init_parser(usage, desc="Snapshot/rollback VMs based on options")
        if not self.default_node:
            options.add_node_options(self.parser)
        else:
            options.add_optional_node_options(self.parser)
        options.add_vmid_options(self.parser)
        options.add_range_options(self.parser)
        self.parser.add_argument(
            '-n', '--snapname',
            type=str,
            help='Name of the snapshot. Default for snapshotting is base. Default for rollback is latest snapshot.'
        )
        self.parser.add_argument(
            '-b', '--rollback',
            action='store_true',
            help='Rollback VM'
        )
        self.parser.add_argument(
            '-d', '--delete',
            action='store_true',
            help='Delete snapshot for VM'
        )
        self.parser.add_argument(
            '-m', '--vmstate',
            action='store_true',
            help='Include RAM in snapshot.'
        )
        self.parser.add_argument(
            '-s', '--start',
            action='store_true',
            help='Start the VM after rolling back.'
        )

    def post_process_args(self, options):
        """Post-process and validate arguments"""
        # Validate node
        if not options.node:
            if self.default_node:
                options.node = self.default_node
            else:
                raise ValidationError("Proxmox node must be set in arguments or in environment variables")
        
        # Validate operation requirements
        if not options.vmid and not options.range:
            raise ValidationError("The 'vmid' argument is required unless -r is set")
        
        # Validate mutually exclusive operations
        operations = sum([bool(options.rollback), bool(options.delete)])
        if operations > 1:
            raise ValidationError("Only one operation can be specified: rollback, delete, or create (default)")
        
        # Validate vmid if provided
        if options.vmid:
            options.vmid = validate_vmid(options.vmid)
        
        # Validate node name
        options.node = validate_node_name(options.node)
        
        # Validate range if provided
        if options.range:
            if len(options.range) != 2:
                raise ValidationError("Range must specify exactly two values")
            options.range = [validate_vmid(options.range[0]), validate_vmid(options.range[1])]
        
        # Validate snapshot name if provided
        if options.snapname:
            options.snapname = validate_snapshot_name(options.snapname)
        
        # Set default snapshot names based on operation
        if not options.snapname:
            if options.rollback:
                # Will be determined later from available snapshots
                options.snapname = None
            else:
                # Default for create/delete operations
                options.snapname = "base"
        
        # Prepare snapshot args based on operation type
        if options.rollback:
            include = {'start', 'snapname', 'vmid'}
        elif options.delete:
            include = {'vmid', 'force', 'snapname'}
        else:  # create snapshot
            include = {'vmstate', 'snapname', 'vmid'}
        
        self.snapshot_args = {
            key: (1 if value is True else 0 if value is False else value) 
            for key, value in vars(options).items() 
            if value is not None and key in include
        }

        return options
    
    def run(self) -> None:
        """Execute the snapshot operation"""
        super().run()
        
        # Determine the operation function
        if self.options.rollback:
            func = self._rollback_snapshot
        elif self.options.delete:
            func = self._delete_snapshot
        else:
            func = self._make_snapshot
        
        try:
            if self.options.vmid:
                # Single VM operation
                func(self.options.node, self.options.vmid, **self.snapshot_args)
            elif self.options.range:
                # Range operation
                results = utils.function_over_range(
                    func, 
                    self.options.range[0], 
                    self.options.range[1], 
                    self.options.node,
                    **self.snapshot_args
                )
                # Log summary
                successful = sum(1 for _, success, _ in results if success)
                total = len(results)
                self.logger.info(f"Operation completed: {successful}/{total} VMs processed successfully")
        except Exception as e:
            self.logger.error(f"Snapshot operation failed: {e}")
            raise
    
    def _rollback_snapshot(self, node: str, vmid: int, snapname: Optional[str] = None, **kwargs) -> None:
        """Rollback VM to a specific snapshot"""
        try:
            node = validate_node_name(node)
            vmid = validate_vmid(vmid)
            
            # If no snapshot name provided, get the latest one
            if not snapname:
                self.logger.debug(f"No snapshot name provided, finding latest for VM {vmid}")
                snapshots = self.prox.nodes(node).qemu(vmid).snapshot.get()
                if not snapshots:
                    raise SnapshotError(f"No snapshots found for VM {vmid}")
                snapname = snapshots[0]["name"]
                self.logger.info(f"Using latest snapshot: {snapname}")
            else:
                snapname = validate_snapshot_name(snapname)
            
            self.logger.info(f"Rolling back VM {vmid} on node {node} to snapshot '{snapname}'")
            task_id = self.prox.nodes(node).qemu(vmid).snapshot(snapname).rollback.post(**kwargs)
            utils.block_until_done(self.prox, task_id, node)
            self.logger.info(f"Successfully rolled back VM {vmid} to snapshot '{snapname}'")
        except Exception as e:
            self.logger.error(f"Failed to rollback VM {vmid} to snapshot '{snapname}': {e}")
            raise SnapshotError(f"Failed to rollback VM {vmid}: {e}")

    def _make_snapshot(self, node: str, vmid: int, snapname: str = "base", **kwargs) -> None:
        """Create a snapshot of the VM"""
        try:
            node = validate_node_name(node)
            vmid = validate_vmid(vmid)
            snapname = validate_snapshot_name(snapname) if snapname else "base"
            
            self.logger.info(f"Creating snapshot '{snapname}' for VM {vmid} on node {node}")
            task_id = self.prox.nodes(node).qemu(vmid).snapshot.post(snapname=snapname, **kwargs)
            utils.block_until_done(self.prox, task_id, node)
            self.logger.info(f"Successfully created snapshot '{snapname}' for VM {vmid}")
        except Exception as e:
            self.logger.error(f"Failed to create snapshot '{snapname}' for VM {vmid}: {e}")
            raise SnapshotError(f"Failed to create snapshot for VM {vmid}: {e}")
    
    def _delete_snapshot(self, node: str, vmid: int, snapname: str = "base", **kwargs) -> None:
        """Delete a specific snapshot"""
        try:
            node = validate_node_name(node)
            vmid = validate_vmid(vmid)
            snapname = validate_snapshot_name(snapname) if snapname else "base"
            
            self.logger.info(f"Deleting snapshot '{snapname}' for VM {vmid} on node {node}")
            task_id = getattr(self.prox.nodes(node).qemu(vmid).snapshot, snapname).delete(**kwargs)
            utils.block_until_done(self.prox, task_id, node)
            self.logger.info(f"Successfully deleted snapshot '{snapname}' for VM {vmid}")
        except Exception as e:
            self.logger.error(f"Failed to delete snapshot '{snapname}' for VM {vmid}: {e}")
            raise SnapshotError(f"Failed to delete snapshot for VM {vmid}: {e}")


def main(args=None):
    Snapshot.cli_executor(args)


if __name__ == "__main__":
    main()