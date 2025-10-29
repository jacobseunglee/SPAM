from abc import ABC, abstractmethod
import arguments.options as options
import sys
from dotenv import load_dotenv
import os
from proxmoxer import ProxmoxAPI
import argparse
import conf.config as config
from utils.exceptions import SpamError, ProxmoxConnectionError, ConfigurationError, ValidationError
from utils.validation import validate_required_string
from typing import Optional

# Logging setup with fallback
try:
    from utils.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class CLI(ABC):
    def __init__(self, args) -> None:
        self.args = args
        self.parser = None
        self.options = None
        self.prox: Optional[ProxmoxAPI] = None
        self.default_node: Optional[str] = None
        self.proxmox_host: Optional[str] = None
        self.proxmox_user: Optional[str] = None
        self.proxmox_pass: Optional[str] = None
        self.proxmox_realm: Optional[str] = None
        self.configpath: Optional[str] = None
        self.logger = logger

    @abstractmethod
    def init_parser(self, usage: str = "", desc: Optional[str] = None) -> None:
        """Initialize the argument parser for this CLI command"""
        if self.parser is None:
            self.parser = options.create_base_parser(self.name, usage=usage, desc=desc)

    def parse(self) -> None:
        """Parse command line arguments"""
        try:
            self.load_env()
            self.init_parser()
            options = self.parser.parse_args(self.args[1:])
            self.options = self.post_process_args(options)
        except ValidationError as e:
            # Show help before validation errors
            self.parser.print_help()
            print()  # Add blank line for readability
            raise SpamError(f"Validation error: {e}")
        except argparse.ArgumentError as e:
            # Show help before argparse errors
            self.parser.print_help()
            print()  # Add blank line for readability
            raise SpamError(f"Argument error: {e}")
        except Exception as e:
            self.parser.print_help()
            print() 
            raise SpamError(f"Failed to parse arguments: {e}")
    
    def connect(self) -> None:
        """Establish connection to Proxmox"""
        try:
            # Validate required connection parameters
            validate_required_string(self.proxmox_host, "PROXMOX_HOST")
            validate_required_string(self.proxmox_user, "PROXMOX_USER")
            validate_required_string(self.proxmox_pass, "PROXMOX_PASSWORD")
            validate_required_string(self.proxmox_realm, "PROXMOX_REALM")
            
            self.logger.debug(f"Connecting to Proxmox at {self.proxmox_host}")
            self.prox = ProxmoxAPI(
                self.proxmox_host, 
                user=f'{self.proxmox_user}@{self.proxmox_realm}', 
                password=self.proxmox_pass, 
                verify_ssl=False
            )
            
            # Test connection
            self.prox.version.get()
            self.logger.info(f"Successfully connected to Proxmox at {self.proxmox_host}")
            
        except Exception as e:
            raise ProxmoxConnectionError(f"Failed to connect to Proxmox: {e}")
    
    def load_env(self) -> None:
        """Load environment variables"""
        try:
            load_dotenv()
            self.proxmox_host = os.getenv('PROXMOX_HOST')
            self.proxmox_user = os.getenv('PROXMOX_USER')
            self.proxmox_pass = os.getenv('PROXMOX_PASSWORD')
            self.proxmox_realm = os.getenv('PROXMOX_REALM', 'pve')  # Default to 'pve'
            self.default_node = os.getenv('PROXMOX_DEFAULT_NODE')
            self.configpath = os.getenv('CONFIG_PATH')
            
            self.logger.debug("Environment variables loaded")
        except Exception as e:
            raise ConfigurationError(f"Failed to load environment: {e}")

    def prep_config(self) -> config.Env:
        """Prepare configuration from file"""
        try:
            if not self.configpath:
                self.configpath = "conf/env.yaml"
            
            self.logger.debug(f"Loading configuration from {self.configpath}")
            conf: dict[str, str] = config.get_config(self.configpath)
            env: config.Env = config.get_env(conf)
            return env
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

    @abstractmethod
    def post_process_args(self, options):
        """Post-process parsed arguments"""
        return options
    
    @abstractmethod
    def run(self):
        """Main execution method - to be implemented by subclasses"""
        self.parse()
        self.connect()

    @classmethod
    def cli_executor(cls, args=None, subparser=None):
        """Execute the CLI command"""
        if args is None:
            args = sys.argv
        try:
            cli = cls(args)
            # If a subparser is provided, set it as the parser and configure it
            if subparser is not None:
                cli.parser = subparser
            cli.run()
        except SpamError as e:
            logger.error(f"SPAM error: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Operation cancelled by user")
            sys.exit(130)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            sys.exit(1)