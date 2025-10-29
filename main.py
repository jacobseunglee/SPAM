#!/usr/bin/env python3
"""
SPAM - Scripting Proxmox Automation Magic
Main entry point for the SPAM CLI application
"""

import sys
import argparse
from typing import List, Optional

from utils.logging_config import configure_spam_logging, get_logger
from utils.exceptions import SpamError


def create_main_parser() -> argparse.ArgumentParser:
    """Create the main argument parser"""
    parser = argparse.ArgumentParser(
        prog='SPAM',
        description='SPAM - Scripting Proxmox Automation Magic',
        epilog='Use "spam <command> --help" for more information about a command.'
    )
    
    parser.add_argument(
        '--version', 
        action='version', 
        version='SPAM 1.0.0'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set the logging level'
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        metavar='<command>'
    )
    
    # Add subcommands
    subparsers.add_parser(
        'clone',
        help='Clone VMs based on configuration or options'
    )
    
    subparsers.add_parser(
        'status', 
        help='Start, stop, or destroy VMs'
    )
    
    subparsers.add_parser(
        'snapshot',
        help='Create, rollback, or delete VM snapshots'
    )
    
    subparsers.add_parser(
        'setup',
        help='Setup and configure SPAM environment'
    )
    
    return parser


def route_command(args: List[str]) -> int:
    """Route commands to appropriate CLI classes"""
    if not args or len(args) < 2:
        # No command specified, show help
        parser = create_main_parser()
        parser.print_help()
        return 1
    
    command = args[1]
    
    try:
        if command == 'clone':
            from clone import Clone
            Clone.cli_executor(args[1:])
        elif command == 'status':
            from status import Status
            Status.cli_executor(args[1:])
        elif command == 'snapshot':
            from snapshot import Snapshot
            Snapshot.cli_executor(args[1:])
        elif command == 'setup':
            from setup import setup_environment
            setup_environment()
        else:
            print(f"Unknown command: {command}")
            parser = create_main_parser()
            parser.print_help()
            return 1
            
    except SpamError as e:
        logger = get_logger(__name__)
        logger.error(f"SPAM error: {e}")
        return 1
    except KeyboardInterrupt:
        logger = get_logger(__name__)
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Unexpected error: {e}")
        if '--verbose' in args or '-v' in args:
            import traceback
            logger.error(traceback.format_exc())
        return 1
    
    return 0


def main() -> int:
    """Main entry point"""
    # Parse initial arguments to get log level
    parser = create_main_parser()
    
    # Parse known args to get logging level early
    known_args, _ = parser.parse_known_args()
    
    # Setup logging
    if hasattr(known_args, 'log_level'):
        import os
        os.environ['SPAM_LOG_LEVEL'] = known_args.log_level
    
    configure_spam_logging()
    logger = get_logger(__name__)
    
    logger.debug(f"Starting SPAM with arguments: {sys.argv}")
    
    # Route to appropriate command
    return route_command(sys.argv)


if __name__ == '__main__':
    sys.exit(main())