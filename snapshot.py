from cli import CLI
import arguments.options as options
import utils.utils as utils
import conf.config as config

class Snapshot(CLI):
    name = "snapshot"
    def __init__(self, args):
        super().__init__(args)

        self.snapshot_args: dict = {}
        self.environment = None


    def init_parser(self, usage: str = "", desc = None) -> None:
        super().init_parser(self.name, desc="Snapshot/rollback VMs based on options")
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
        # do post processing here
        if not options.node:
            if self.default_node:
                options.node = self.default_node
            else:
                self.parser.error("Proxmox node must be set in arguments or in environment variables")
        if not options.vmid and not options.range:
            self.parser.error("The 'vmid' argument are required unless -r is set.")
        if options.rollback:
            include: set[str] = {'start', 'snapname', 'vmid'}
        elif options.delete:
            include: set[str] = {'vmid','force', 'snapname'}
        else:
            include: set[str] = {'vmstate', 'snapname', 'vmid'}
        self.snapshot_args: dict[str,str] = {key: (1 if value is True else 0 if value is False else value) for key, value in vars(options).items() if value is not None and key in include}

        return options
    
    def run(self) -> None:
        super().run()
        if self.options.rollback:
            func = self._rollback_snapshot
        elif self.options.delete:
            func = self._delete_snapshot
        else:
            func = self._make_snapshot
        
        if self.options.vmid:
            func(self.options.node, **self.snapshot_args)
        else:
            utils.function_over_range(func, self.options.range[0], self.options.range[1], self.options.node, **self.snapshot_args)

        return
    
    def _rollback_snapshot(self, node: str, snapname: str = "", vmid: int = -1, **kwargs) -> None:
        try:
            if snapname == "":
                snapshots = self.prox.nodes(node).qemu(vmid).snapshot.get()
                snapname = snapshots[0]["name"]
            task_id = self.prox.nodes(node).qemu(vmid).snapshot(snapname).rollback.post(**kwargs)
            utils.block_until_done(self.prox, task_id, node)
            print(f"Rolling back VMID {vmid} in {node} to {snapname} snapshot.")
        except Exception as e:
            print(e)
        return


    def _make_snapshot(self, node: str, snapname: str = "base", vmid: int = -1, **kwargs):
        try:
            task_id = self.prox.nodes(node).qemu(vmid).snapshot.post(snapname=snapname,**kwargs)
            utils.block_until_done(self.prox, task_id, node)
            print(f"Snapshotting VMID {vmid} in {node} as {snapname} snapshot.")
        except Exception as e:
            print(e)
        return
    
    def _delete_snapshot(self, node: str, snapname: str = "base", vmid: int = -1, **kwargs):
        try:
            task_id = getattr(self.prox.nodes(node).qemu(vmid).snapshot, snapname).delete(**kwargs)
            utils.block_until_done(self.prox, task_id, node)
            print(f"Deleting snapshot {snapname} for VMID {vmid} in {node}.")
        except Exception as e:
            print(e)
        return
   

def main(args=None):
    Snapshot.cli_executor(args)


if __name__ == "__main__":
    main()

