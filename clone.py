"""VM Cloning for SPAM"""

import math
from typing import Optional
from cli import CLI
import arguments.options as options
import utils.cloudinit as cloudinit
import utils.utils as utils
import conf.config as config
from utils.exceptions import ValidationError, ProxmoxAPIError, CloneError
from utils.validation import validate_vmid, validate_node_name, validate_vm_name


class Clone(CLI):
    name = "clone"

    def __init__(self, args):
        super().__init__(args)
        self.clone_args: dict = {}
        self.environment: Optional[config.Env] = None

    def init_parser(self, usage: str = "", desc: Optional[str] = None) -> None:
        super().init_parser(
            usage,
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
        """Post-process and validate arguments"""
        # Set default node if not provided
        if not options.node:
            if self.default_node:
                options.node = self.default_node
            else:
                # For environment/workshop modes, node is not always required upfront
                if not any([options.environment, options.workshop, options.ccdctraining]):
                    raise ValidationError("Node must be specified when not using environment mode")
        
        # Validate required arguments for direct cloning
        if not any([options.environment, options.workshop, options.ccdctraining]):
            if not all([options.node, options.vmid, options.newid]):
                raise ValidationError(
                    "The 'node', 'vmid' and 'newid' arguments are required unless using environment mode"
                )
            
            # Validate the provided arguments
            options.vmid = validate_vmid(options.vmid)
            options.newid = validate_vmid(options.newid)
            options.node = validate_node_name(options.node)
            
            # Validate name if provided
            if options.name:
                options.name = validate_vm_name(options.name)
        
        # Validate target node if provided
        if options.target:
            options.target = validate_node_name(options.target)
        
        # Prepare clone arguments
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
            "description",
            "format",
        }
        self.clone_args = {
            key: (1 if value is True else 0 if value is False else value)
            for key, value in vars(options).items()
            if value is not None and key in include
        }

        # Load environment configuration if needed
        if options.environment or options.ccdctraining:
            self.environment = self.prep_config()
        
        return options

    def run(self) -> None:
        """Execute the clone operation"""
        super().run()
        
        try:
            if self.options.environment:
                self._clone_env()
            elif self.options.workshop:
                self._clone_workshop()
            elif self.options.ccdctraining:
                self._clone_training()
            else:
                self._clone_vm(self.options.vmid, **self.clone_args)
        except Exception as e:
            self.logger.error(f"Clone operation failed: {e}")
            raise

    def _clone_vm(self, vmid: int, **kwargs) -> None:
        """Clone a single VM"""
        try:
            vmid = validate_vmid(vmid)
            
            # Get the node where the source VM is located
            node = utils.get_vm_node(self.prox, vmid)
            
            self.logger.info(f"Cloning VM {vmid} from node {node}")
            task_id = self.prox.nodes(node).qemu(vmid).clone.create(**kwargs)
            
            target = node if "target" not in kwargs else kwargs["target"]
            newid = kwargs.get('newid', 'unknown')
            
            self.logger.info(f"Cloning VM {vmid} on {node} to VM {newid} on {target}")
            utils.block_until_done(self.prox, task_id, target if target != node else node)
            self.logger.info(f"Successfully cloned VM {vmid} to VM {newid}")
        except Exception as e:
            self.logger.error(f"Failed to clone VM {vmid}: {e}")
            raise CloneError(f"Failed to clone VM {vmid}: {e}")

    def _get_vm_node(self, vmid: int) -> str:
        """Get the node where a VM is located - DEPRECATED: Use utils.get_vm_node instead"""
        self.logger.warning("_get_vm_node is deprecated, use utils.get_vm_node instead")
        return utils.get_vm_node(self.prox, vmid)

    def _get_vm_config(self, vmid: int) -> dict:
        """Get VM configuration - DEPRECATED: Use utils.get_vm_config instead"""
        self.logger.warning("_get_vm_config is deprecated, use utils.get_vm_config instead")
        return utils.get_vm_config(self.prox, vmid)

    def _clone_env(self) -> None:
        """Clone VMs based on environment configuration"""
        if not self.environment:
            raise ValidationError("Environment configuration not loaded")
        
        self.logger.info(f"Starting environment cloning across {len(self.environment.nodes)} nodes")
        
        try:
            for node in self.environment.nodes:
                node = validate_node_name(node)
                for box in self.environment.boxes:
                    self.logger.info(f"Cloning box {box.id} to node {node}")
                    self._clone_vm(box.id, target=node, **box.config)
                    
                    # Apply cloud-init configuration if specified
                    if box.cloud:
                        self.logger.info(f"Applying cloud-init configuration for VM {box.config['newid']}")
                        cloudinit.set_cloudinit(
                            self.prox, node, box.config["newid"], **box.cloud
                        )
            
            self.logger.info("Environment cloning completed successfully")
        except Exception as e:
            self.logger.error(f"Environment cloning failed: {e}")
            raise CloneError(f"Environment cloning failed: {e}")

    def _clone_workshop(self) -> None:
        """Interactive workshop cloning mode"""
        try:
            self.logger.info("Starting interactive workshop cloning")
            
            template = input("Enter the VMID of the template you want to clone: ")
            template = validate_vmid(template)
            
            node = input(f"Node name where template VM is (Default: {self.default_node}): ").strip()
            if not node:
                node = self.default_node
            if not node:
                raise ValidationError("Source node must be specified")
            node = validate_node_name(node)
            
            target_node = input(f"Target node name where cloned VMs will be (Default: {node}): ").strip()
            if not target_node:
                target_node = node
            target_node = validate_node_name(target_node)
            
            copies = int(input("Number of clones: "))
            if copies <= 0 or copies > 100:
                raise ValidationError("Number of copies must be between 1 and 100")
            
            newid = int(input("First VMID of target VM: "))
            newid = validate_vmid(newid)
            
            name = input("Name of clone (Will be in format {Name}-{number}): ").strip()
            if name:
                name = validate_vm_name(name)
            
            ip = input("IP address format (use X to signify variable number): ").strip()
            subnet = input("Subnet mask (/24, /8?): ").strip()
            gateway = input("Gateway: ").strip()
            bridge = input("Bridge: ").strip()
            os_type = input("OS type (windows or linux): ").strip().lower()
            
            if os_type not in ['windows', 'linux']:
                raise ValidationError("OS type must be 'windows' or 'linux'")

            # Confirm the operation
            confirm = input(
                f"Cloning VMID {template} {copies} times to VMID {newid} to {newid + copies - 1}.\n"
                f"IP addresses will start from {ip.replace('X', '1')} to {ip.replace('X', str(copies))} (Y/N): "
            )
            
            if confirm.upper() != 'Y':
                self.logger.info("Workshop cloning cancelled by user")
                return
            
            self.logger.info(f"Starting workshop cloning: {copies} copies of VM {template}")
            
            for i in range(1, copies + 1):
                vm_name = f"{name}-{i}" if name else None
                self._clone_vm(
                    template,
                    newid=newid + i - 1,
                    target=target_node,
                    name=vm_name,
                )
                
                # Apply cloud-init configuration
                if ip and gateway and bridge:
                    self.logger.info(f"Applying cloud-init for VM {newid + i - 1}")
                    cloudinit.set_cloudinit(
                        self.prox,
                        target_node,
                        newid + i - 1,
                        ipconfig0=f"ip={ip.replace('X', str(i))}{subnet},gw={gateway}",
                        net0=f"model={'virtio' if os_type == 'linux' else 'e1000e'},bridge={bridge}",
                    )
            
            self.logger.info("Workshop cloning completed successfully")
        except Exception as e:
            self.logger.error(f"Workshop cloning failed: {e}")
            raise CloneError(f"Workshop cloning failed: {e}")

    def _clone_training(self) -> None:
        """Clone training environment with multiple copies across nodes"""
        if not self.environment:
            raise ValidationError("Environment configuration not loaded for training mode")
        
        try:
            copies = int(self.environment.env["copies"])
            vmid = int(self.environment.env["vmid_start"])
            size = len(self.environment.boxes)

            router_ip = self.environment.env["router_ip"]
            gw = self.environment.env["gw"]
            bridge = int(self.environment.env["bridge_start"])
            router = None
            clone_count = 0
            
            # Show confirmation dialog
            bridge_end = bridge + math.ceil(copies / len(self.environment.nodes)) - 1
            router_end = router_ip.replace('X', str(copies))
            
            self.logger.info(
                f"Planning to clone {copies} copies of environment starting from VMID {vmid} to {vmid + size * copies - 1}"
            )
            self.logger.info(f"Will use bridges vmbr{bridge} to vmbr{bridge_end} across nodes {', '.join(self.environment.nodes)}")
            self.logger.info(f"Router IPs will span {router_ip.replace('X', '1')} to {router_end}")
            
            confirm = input("Continue? (Y/N): ")
            if confirm.upper() != 'Y':
                self.logger.info("Training cloning cancelled by user")
                return
            
            # Find router VM (VM with net1 interface)
            for box in self.environment.boxes:
                try:
                    config = utils.get_vm_config(self.prox, box.id)
                    if "net1" in config:
                        router = box.id
                        self.logger.info(f"Identified router VM: {router}")
                        break
                except Exception:
                    continue
            
            self.logger.info(f"Starting training cloning: {copies} copies across {len(self.environment.nodes)} nodes")
            
            while clone_count < copies:
                for node in self.environment.nodes:
                    node = validate_node_name(node)
                    for box in self.environment.boxes:
                        try:
                            config = utils.get_vm_config(self.prox, box.id)
                            vm_name = validate_vm_name(f"{config.get('name', 'vm')}-{clone_count + 1}")
                            self.logger.info(f"Cloning VM {box.id} to {vmid} on node {node}")
                            self._clone_vm(
                                box.id,
                                newid=vmid,
                                target=node,
                                name=vm_name,
                            )
                            
                            # Configure networking
                            if router == box.id:
                                # This is the router VM
                                cloudinit.set_cloudinit(
                                    self.prox,
                                    node,
                                    vmid,
                                    ipconfig0=f"ip={router_ip.replace('X', str(clone_count + 1))},gw={gw}",
                                    net1=f"model=virtio,bridge=vmbr{bridge}",
                                )
                            else:
                                # Regular VM
                                net_config = config.get("net0", "")
                                model = "virtio"  # Default
                                if net_config:
                                    model = net_config.split(",")[0].split("=")[1] if "=" in net_config.split(",")[0] else "virtio"

                                cloudinit.set_cloudinit(
                                    self.prox,
                                    node,
                                    vmid,
                                    net0=f"model={model},bridge=vmbr{bridge}",
                                )
                            
                            # Create base snapshot
                            self.logger.info(f"Creating base snapshot for VM {vmid}")
                            self.prox.nodes(node).qemu(vmid).snapshot.post(
                                snapname="base", vmstate=0
                            )
                            
                            vmid += 1
                        except Exception as e:
                            self.logger.error(f"Failed to clone box {box.id}: {e}")
                            raise
                    
                    clone_count += 1
                    if clone_count >= copies:
                        break
                bridge += 1
            
            self.logger.info("Training cloning completed successfully")
        except KeyError as e:
            raise ValidationError(f"Missing required environment configuration: {e}")
        except Exception as e:
            self.logger.error(f"Training cloning failed: {e}")
            raise CloneError(f"Training cloning failed: {e}")


def main(args=None):
    Clone.cli_executor(args)


if __name__ == "__main__":
    main()
