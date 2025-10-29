
"""VM Status Management for SPAM"""

from typing import Optional, Callable
from cli import CLI
import arguments.options as options
import utils.utils as utils
import conf.config as config
from utils.exceptions import ValidationError, ProxmoxAPIError
from utils.validation import validate_vmid, validate_node_name


class Status(CLI):
    name = "status"
    
    def __init__(self, args):
        super().__init__(args)
        self.status_args: dict = {}
        self.environment: Optional[config.Env] = None

    def init_parser(self, usage: str = "", desc: Optional[str] = None) -> None:
        super().init_parser(usage, desc="Operations on VMs")
        if not self.default_node:
            options.add_node_options(self.parser)
        else:
            options.add_optional_node_options(self.parser)
        options.add_vmid_options(self.parser)
        options.add_range_options(self.parser)
        self.parser.add_argument(
            '-p', '--stop',
            action='store_true',
            help='Stop the VMs'
        )
        self.parser.add_argument(
            '-d', '--destroy',
            action='store_true',
            help='Destroy the VMs'
        )
        self.parser.add_argument(
            '-s', '--start',
            action='store_true',
            help='Start the VMs.'
        )
        self.parser.add_argument(
            '-c', '--crossnode',
            action='store_true',
            help='Use option to apply configuration settings across different nodes created from training cloning.'
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
        if not options.vmid and not options.range and not options.crossnode:
            raise ValidationError("The 'vmid' argument is required unless -r or --crossnode is set")
        
        # Validate that at least one operation is specified
        if not any([options.start, options.stop, options.destroy]):
            raise ValidationError("Must specify an operation: --start, --stop, or --destroy")
        
        # Validate mutually exclusive operations
        operations = sum([bool(options.start), bool(options.stop), bool(options.destroy)])
        if operations > 1:
            raise ValidationError("Only one operation can be specified at a time")
        
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
        
        # Prepare status args (currently empty, but could be extended)
        include = set()  # Add relevant argument keys here if needed
        self.status_args = {
            key: (1 if value is True else 0 if value is False else value) 
            for key, value in vars(options).items() 
            if value is not None and key in include
        }

        # Load environment configuration if crossnode operation
        if options.crossnode:
            self.environment = self.prep_config()

        return options
    
    def run(self) -> None:
        """Execute the status operation"""
        super().run()
        
        # Determine the operation function
        if self.options.start:
            func = self._start_vm
        elif self.options.stop:
            func = self._stop_vm
        elif self.options.destroy:
            func = self._destroy_vm
        
        try:
            if self.options.vmid:
                # Single VM operation
                func(self.options.node, self.options.vmid)
            elif self.options.crossnode:
                # Cross-node operation
                self._apply_crossnode(func)
            elif self.options.range:
                # Range operation
                results = utils.function_over_range(
                    func, 
                    self.options.range[0], 
                    self.options.range[1], 
                    self.options.node,
                    **self.status_args
                )
                # Log summary
                successful = sum(1 for _, success, _ in results if success)
                total = len(results)
                self.logger.info(f"Operation completed: {successful}/{total} VMs processed successfully")
        except Exception as e:
            self.logger.error(f"Operation failed: {e}")
            raise
    
    def _start_vm(self, node: str, vmid: int) -> None:
        """Start a single VM"""
        try:
            node = validate_node_name(node)
            vmid = validate_vmid(vmid)
            
            self.logger.info(f"Starting VM {vmid} on node {node}")
            task_id = self.prox.nodes(node).qemu(vmid).status.start.post()
            utils.block_until_done(self.prox, task_id, node)
            self.logger.info(f"Successfully started VM {vmid} on node {node}")
        except Exception as e:
            self.logger.error(f"Failed to start VM {vmid} on node {node}: {e}")
            raise ProxmoxAPIError(f"Failed to start VM {vmid}: {e}")

    def _stop_vm(self, node: str, vmid: int) -> None:
        """Stop a single VM"""
        try:
            node = validate_node_name(node)
            vmid = validate_vmid(vmid)
            
            self.logger.info(f"Stopping VM {vmid} on node {node}")
            task_id = self.prox.nodes(node).qemu(vmid).status.stop.post()
            utils.block_until_done(self.prox, task_id, node)
            self.logger.info(f"Successfully stopped VM {vmid} on node {node}")
        except Exception as e:
            self.logger.error(f"Failed to stop VM {vmid} on node {node}: {e}")
            raise ProxmoxAPIError(f"Failed to stop VM {vmid}: {e}")

    def _destroy_vm(self, node: str, vmid: int) -> None:
        """Destroy a single VM (stop then delete)"""
        try:
            node = validate_node_name(node)
            vmid = validate_vmid(vmid)
            
            self.logger.info(f"Destroying VM {vmid} on node {node}")
            
            # First stop the VM
            try:
                self._stop_vm(node, vmid)
            except ProxmoxAPIError:
                # VM might already be stopped, continue with deletion
                self.logger.warning(f"Could not stop VM {vmid}, attempting deletion anyway")
            
            # Then delete it
            task_id = self.prox.nodes(node).qemu(vmid).delete()
            utils.block_until_done(self.prox, task_id, node)
            self.logger.info(f"Successfully destroyed VM {vmid} on node {node}")
        except Exception as e:
            self.logger.error(f"Failed to destroy VM {vmid} on node {node}: {e}")
            raise ProxmoxAPIError(f"Failed to destroy VM {vmid}: {e}")
    
    def _apply_crossnode(self, func: Callable) -> None:
        """Apply operation across multiple nodes for training environments"""
        if not self.environment:
            raise ValidationError("Environment configuration not loaded for crossnode operation")
        
        try:
            copies = int(self.environment.env["copies"])
            vmid = int(self.environment.env["vmid_start"])
            current = 0
            
            self.logger.info(f"Starting crossnode operation for {copies} copies")
            
            while current < copies:
                for node in self.environment.nodes:
                    for _ in self.environment.boxes:
                        func(node, vmid)
                        vmid += 1
                    current += 1
                    if current >= copies:
                        break
            
            self.logger.info("Crossnode operation completed successfully")
        except KeyError as e:
            raise ValidationError(f"Missing required configuration key: {e}")
        except Exception as e:
            self.logger.error(f"Crossnode operation failed: {e}")
            raise

def main(args=None):
    Status.cli_executor(args)


if __name__ == "__main__":
    main()


