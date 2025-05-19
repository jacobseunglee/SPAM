import math

from cli import CLI
import arguments.options as options
import utils.cloudinit as cloudinit
import utils.utils as utils
import conf.config as config


class Clone(CLI):
    name = "clone"

    def __init__(self, args):
        super().__init__(args)

        self.clone_args: dict = {}
        self.environment = None

    def init_parser(self, usage: str = "", desc=None) -> None:
        super().init_parser(
            self.name,
            desc="Clones VMs based on configuration file or options, used for workshops and CCDC mock environments",
        )
        options.add_environment_file_options(self.parser)
        options.add_name_options(self.parser)
        options.add_vmid_options(self.parser)
        options.add_newid_options(self.parser)
        if not self.default_node:
            options.add_node_options(self.parser)
        else:
            options.add_optional_node_options(self.parser)
        options.add_pool_options(self.parser)
        options.add_target_node_options(self.parser)
        self.parser.add_argument(
            "-f",
            "--full",
            action="store_true",
            help="Create a full copy of all disks. This is always done when you clone a normal VM. For VM templates, it will try to create a linked clone by default.",
        )
        self.parser.add_argument(
            "-s", "--snapshot", type=str, help="The name of the snapshot to clone."
        )
        self.parser.add_argument(
            "-w",
            "--workshop",
            type=str,
            nargs="?",
            const="conf/workshop.yaml",
            help="Cloning workshops",
        )
        self.parser.add_argument(
            "-c",
            "--ccdctraining",
            type=str,
            nargs="?",
            const="conf/training.yaml",
            help="Cloning ccdc training",
        )

    def post_process_args(self, options):
        # do post processing here
        if not options.node:
            options.node = self.default_node
        if (
            (not options.node or not options.vmid or not options.newid)
            and not options.environment
            and not options.workshop
            and not options.ccdctraining
        ):
            self.parser.error(
                "The 'node', 'vmid' and 'newid' arguments are required unless -e is set."
            )
        include: set[str] = {
            "newid",
            "snapshot",
            "target",
            "full",
            "pool",
            "name",
            "bwlimit",
            "snapname",
            "storage",
            "target",
            "description",
            "format",
        }
        self.clone_args: dict[str, str] = {
            key: (1 if value is True else 0 if value is False else value)
            for key, value in vars(options).items()
            if value is not None and key in include
        }

        if options.environment or options.ccdctraining:
            self.environment = self.prep_config()
        return options

    def run(self) -> None:
        super().run()
        if self.options.environment:
            self._clone_env()
        elif self.options.workshop:
            self._clone_workshop()
        elif self.options.ccdctraining:
            self._clone_training()
        else:
            self._clone_vm(self.options.vmid, **self.clone_args)
        return

    def _clone_vm(self, vmid: str, **kwargs) -> None:
        vms = self.prox.cluster.resources.get(type="vm")
        try:
            node = self._get_vm_node(vmid)
            task_id = self.prox.nodes(node).qemu(vmid).clone.create(**kwargs)
            target = node if "target" not in kwargs else kwargs["target"]
            print(
                f"Cloning VMID {vmid} in {node} to VMID {kwargs['newid']} in {target}"
            )
            utils.block_until_done(self.prox, task_id, node)
        except Exception as e:
            print(e)
        return

    def _get_vm_node(self, vmid: str) -> str:
        vms = self.prox.cluster.resources.get(type="vm")
        for vm in vms:
            if str(vm["vmid"]) == vmid:
                return vm["node"]

        raise FileNotFoundError("VMID not found in cluster")

    def _get_vm_config(self, vmid: str) -> dict:
        node = self._get_vm_node(vmid)
        return self.prox.nodes(node).qemu(vmid).config.get()

    def _clone_env(self) -> None:
        for node in self.environment.nodes:
            for box in self.environment.boxes:
                self._clone_vm(box.id, target=node, **box.config)
                if box.cloud:
                    cloudinit.set_cloudinit(
                        self.prox, node, box.config["newid"], **box.cloud
                    )
        return

    def _clone_workshop(self) -> None:
        template = input("Enter the VMID of the template you want to clone: ")
        node = input(f"Node name where template VM is (Default: {self.default_node}): ")
        if not node:
            node = self.default_node
        target_node = input(
            f"Target node name where cloned VMs will be (Default: {node}): "
        )
        if not target_node:
            target_node = node
        copies = int(input("Number of clones: "))
        newid = int(input("First VMID of target VM: "))
        name = input("Name of clone (Will be in format {Name}-{number}): ")
        ip = input("IP address format (use X to signify variable number): ")
        subnet = input("Subnet mask (/24, /8?): ")
        gateway = input("Gateway: ")
        bridge = input("bridge: ")
        os = input("windows or linux: ")

        confirm = input(
            f"Cloning VMID {template} {copies} times to VMID {newid} to {newid + copies - 1}.\nIP addresses will start from {ip.replace('X', '1')} to {ip.replace('X', str(1 + copies - 1))} (Y/N): "
        )
        if confirm == "Y":
            for i in range(1, 1 + copies):
                self._clone_vm(
                    template,
                    newid=newid + i - 1,
                    target=target_node,
                    name=f"{name}-{i}",
                )
                cloudinit.set_cloudinit(
                    self.prox,
                    node,
                    newid + i - 1,
                    ipconfig0=f"ip={ip.replace('X', str(i))}{subnet},gw={gateway}",
                    net0=f"model={'virtio' if os == 'linux' else 'e1000e'},bridge={bridge}",
                )

    def _clone_training(self) -> None:
        copies = int(self.environment.env["copies"])
        vmid = int(self.environment.env["vmid_start"])
        size = len(self.environment.boxes)

        router_ip = self.environment.env["router_ip"]
        gw = self.environment.env["gw"]
        bridge = int(self.environment.env["bridge_start"])
        router = None
        clone_count = 0
        if (
            input(
                f"Cloning {copies} copies of this environment, starting from VMID {vmid} to {vmid + size * copies - 1}.\n\
Will be using vmbr{bridge} to vmbr{bridge + (math.ceil(copies / len(self.environment.nodes))) - 1} across nodes {', '.join(self.environment.nodes)}\n\
Router IPs will span {router_ip.replace('X', '1')} to {router_ip.replace('X', str(copies))}\n\
Y to continue any other key to quit: "
            )
            != "Y"
        ):
            return
        for box in self.environment.boxes:
            id = box.id
            if "net1" in self._get_vm_config(id):
                router = id
                break
        while clone_count < copies:
            for node in self.environment.nodes:
                for box in self.environment.boxes:
                    conf = self._get_vm_config(box.id)
                    self._clone_vm(
                        box.id,
                        newid=vmid,
                        target=node,
                        name=f"{conf['name']}-{clone_count + 1}",
                    )
                    if router == box.id:
                        cloudinit.set_cloudinit(
                            self.prox,
                            node,
                            vmid,
                            ipconfig0=f"ip={router_ip.replace('X', str(clone_count + 1))},gw={gw}",
                            net1=f"model=virtio,bridge=vmbr{bridge}",
                        )
                    else:
                        net = self._get_vm_config(str(vmid))["net0"]
                        model = net.split(",")[0].split("=")[0]

                        cloudinit.set_cloudinit(
                            self.prox,
                            node,
                            vmid,
                            net0=f"model={model},bridge=vmbr{bridge}",
                        )
                    self.prox.nodes(node).qemu(vmid).snapshot.post(
                        snapname="base", vmstate=0
                    )
                    vmid += 1
                clone_count += 1
                if clone_count >= copies:
                    break
            bridge += 1


def main(args=None):
    Clone.cli_executor(args)


if __name__ == "__main__":
    main()
