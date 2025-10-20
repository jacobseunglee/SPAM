from cli import CLI
import arguments.options as options
import utils.utils as utils
import conf.config as config


class Status(CLI):
    name = "status"

    def __init__(self, args):
        super().__init__(args)

        self.status_args: dict = {}
        self.environment = None

    def init_parser(self, usage: str = "", desc=None) -> None:
        super().init_parser(self.name, desc="Operations on VMs")
        if not self.default_node:
            options.add_node_options(self.parser)
        else:
            options.add_optional_node_options(self.parser)
        options.add_vmid_options(self.parser)
        options.add_range_options(self.parser)
        self.parser.add_argument(
            "-p", "--stop", action="store_true", help="Stop the VMs"
        )
        self.parser.add_argument(
            "-d", "--destroy", action="store_true", help="Destroy the VMs"
        )
        self.parser.add_argument(
            "-s", "--start", action="store_true", help="Start the VMs."
        )
        self.parser.add_argument(
            "--revert",
            action="store_true",
            help="Revert VMs to their most recent snapshot.",
        )
        self.parser.add_argument(
            "-c",
            "--crossnode",
            action="store_true",
            help="Use option to apply configuration settings across different nodes created from training cloning.",
        )

    def post_process_args(self, options):
        # do post processing here
        if not options.node:
            if self.default_node:
                options.node = self.default_node
            else:
                self.parser.error(
                    "Proxmox node must be set in arguments or in environment variables"
                )
        if not options.vmid and not options.range and not options.crossnode:
            self.parser.error("The 'vmid' argument are required unless -r is set.")
        include = {}
        self.status_args: dict[str, str] = {
            key: (1 if value is True else 0 if value is False else value)
            for key, value in vars(options).items()
            if value is not None and key in include
        }

        if options.crossnode:
            self.environment = self.prep_config()

        return options

    def run(self) -> None:
        super().run()
        if self.options.start:
            func = self._start_vm
        elif self.options.stop:
            func = self._stop_vm
        elif self.options.destroy:
            func = self._destroy_vm
        elif self.options.revert:
            func = self._revert_vm

        if self.options.vmid:
            func(self.options.node, **self.snapshot_args)
        elif self.options.crossnode:
            self._apply_crossnode(func)
        else:
            utils.function_over_range(
                func,
                self.options.range[0],
                self.options.range[1],
                self.options.node,
                **self.status_args,
            )

        return

    def _start_vm(self, node: str, vmid: int = -1) -> None:
        try:
            task_id = self.prox.nodes(node).qemu(vmid).status.start.post()
            utils.block_until_done(self.prox, task_id, node)
            print(f"Starting VMID {vmid} in {node}")
        except Exception as e:
            print(e)
        return

    def _stop_vm(self, node: str, vmid: int = -1) -> None:
        try:
            task_id = self.prox.nodes(node).qemu(vmid).status.stop.post()
            utils.block_until_done(self.prox, task_id, node)
            print(f"Stopping VMID {vmid} in {node}")
        except Exception as e:
            print(e)

    def _destroy_vm(self, node: str, vmid: int = -1) -> None:
        args = {
            "destroy-unreferenced-disks": 1,
            "purge": 1,
        }
        try:
            self._stop_vm(node, vmid)
            task_id = self.prox.nodes(node).qemu(vmid).delete(**args)
            utils.block_until_done(self.prox, task_id, node)
            print(f"Destroying VMID {vmid} in {node}")
        except Exception as e:
            print(e)

    def _revert_vm(self, node: str, vmid: int = -1) -> None:
        try:
            self._stop_vm(node, vmid)
            snaps = self.prox.nodes(node).qemu(vmid).snapshot.get()
            name = None
            for snap in snaps:
                if "parent" not in snap and "name" in snap:
                    name = snap["name"]

            if name is None:
                raise Exception("No snapshot found with no parent")

            task_id = self.prox.nodes(node).qemu(vmid).snapshot(name).rollback.post()
            utils.block_until_done(self.prox, task_id, node)
            print(f"Reverting VMID {vmid} to snapshot {name} in {node}")
        except Exception as e:
            print(e)

    def _apply_crossnode(self, func) -> None:
        copies = int(self.environment.env["copies"])
        vmid = int(self.environment.env["vmid_start"])
        current = 0
        template_ids = []
        for box in self.environment.boxes:
            resource = self.get_vm_resource(box.id)
            node = resource["node"]
            if resource["template"] == 1:
                template_ids.append(box.id)
            else:
                template_ids.append(vmid)
                vmid += 1
        while current < copies:
            for node in self.environment.nodes:
                for _ in template_ids:
                    func(node, vmid)
                    vmid += 1
                current += 1
                if current >= copies:
                    break


def main(args=None):
    Status.cli_executor(args)


if __name__ == "__main__":
    main()
