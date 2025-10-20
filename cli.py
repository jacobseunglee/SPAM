from abc import ABC, abstractmethod
import arguments.options as options
import sys
from dotenv import load_dotenv
import os
from proxmoxer import ProxmoxAPI
import conf.config as config
# Inspiration from Ansible code structure

class CLI(ABC):
    def __init__(self, args) -> None:
        self.args = args
        self.parser = None
        self.options = None
        self.prox = None
        self.default_node = None
        self.proxmox_host = None
        self.proxmox_user = None
        self.proxmox_pass = None
        self.proxmox_realm = None


    @abstractmethod
    def init_parser(self, usage: str = "", desc = None) -> None:
        self.parser = options.create_base_parser(self.name, usage=usage, desc=desc)

    def parse(self) -> None:
        self.load_env()
        self.init_parser()
        options = self.parser.parse_args(self.args[1:])
        self.options = self.post_process_args(options)
    
    def connect(self):
        self.prox: ProxmoxAPI = ProxmoxAPI(self.promxox_host, user=f'{self.proxmox_user}@{self.proxmox_realm}', password=self.proxmox_pass, verify_ssl=False)
    
    def load_env(self) -> None:
        load_dotenv()
        self.promxox_host = os.getenv('PROXMOX_HOST')
        self.proxmox_user = os.getenv('PROXMOX_USER')
        self.proxmox_pass = os.getenv('PROXMOX_PASSWORD')
        self.proxmox_realm = os.getenv('PROXMOX_REALM')
        self.default_node = os.getenv('PROXMOX_DEFAULT_NODE')
        self.configpath = os.getenv('CONFIG_PATH')

    def prep_config(self) -> config.Env:
        if not self.configpath:
            self.configpath = "conf/env.yaml"
        conf: dict[str,str] = config.get_config(self.configpath)
        env: config.Env = config.get_env(conf)
        return env

    @abstractmethod
    def post_process_args(self, options):
        # do post processing here
        return options
    
    @abstractmethod
    def run(self):
        self.parse()
        self.connect()

    @classmethod
    def cli_executor(cls, args=None):
        if args is None:
            args = sys.argv
        cli = cls(args)
        cli.run()

    def get_vm_resource(self, vmid: str) -> dict:
        vms = self.prox.cluster.resources.get(type="vm")
        for vm in vms:
            if str(vm["vmid"]) == vmid:
                return vm

        raise FileNotFoundError("VMID not found in cluster")

    def get_vm_config(self, vmid: str) -> dict:
        node = self.get_vm_resource(vmid)["node"]
        return self.prox.nodes(node).qemu(vmid).config.get()


# add method to connect to proxmox 

# add block until done here
