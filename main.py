#!/usr/bin/env python3
"""
SPAM - Scripting Proxmox Automation Magic
Main entry point for the SPAM CLI application
"""

import sys
import argparse

from utils.logging_config import configure_spam_logging, get_logger
from utils.exceptions import SpamError


def create_main_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with subparsers"""
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
        metavar='<command>',
        required=True
    )
    
    # Create individual subparsers and store them in a map
    subparser_map = {}
    
    subparser_map['clone'] = subparsers.add_parser(
        'clone',
        help='Clone VMs based on configuration or options'
    )
    
    subparser_map['status'] = subparsers.add_parser(
        'status', 
        help='Start, stop, or destroy VMs'
    )
    
    subparser_map['snapshot'] = subparsers.add_parser(
        'snapshot',
        help='Create, rollback, or delete VM snapshots'
    )
    
    subparser_map['setup'] = subparsers.add_parser(
        'setup',
        help='Setup and configure SPAM environment'
    )
    
    # Store the subparser map on the parser for later access
    parser._subparser_map = subparser_map
    
    return parser


def extract_global_args() -> tuple[str, bool, list[str]]:
    """Extract global arguments manually without interfering with subparsers"""
    log_level = 'INFO'
    verbose = False
    remaining_args = []
    
    i = 1  # Skip script name
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        if arg == '--log-level' and i + 1 < len(sys.argv):
            log_level = sys.argv[i + 1]
            i += 2  # Skip both --log-level and its value
        elif arg.startswith('--log-level='):
            log_level = arg.split('=', 1)[1]
            i += 1
        elif arg in ['--verbose', '-v']:
            verbose = True
            i += 1
        elif arg == '--version':
            print('SPAM 1.0.0')
            sys.exit(0)
        elif arg == '--help' or arg == '-h':
            # If help is requested without a command, show main help
            remaining_args.append(arg)
            i += 1
        else:
            # Keep all other arguments for subparser processing
            remaining_args.append(arg)
            i += 1
    
    return log_level, verbose, remaining_args


def find_command_in_args(args: list[str]) -> tuple[str | None, int]:
    """Find the command in the argument list"""
    commands = ['clone', 'status', 'snapshot', 'setup']
    
    for i, arg in enumerate(args):
        if arg in commands:
            return arg, i
    
    return None, -1


def main() -> int:
    """Main entry point"""   
    # Extract global arguments manually
    log_level, verbose, remaining_args = extract_global_args()
    
    # Setup logging based on extracted arguments
    import os
    os.environ['SPAM_LOG_LEVEL'] = log_level
    
    configure_spam_logging()
    logger = get_logger(__name__)
    
    logger.debug(f"Starting SPAM with arguments: {sys.argv}")
    logger.debug(f"Extracted log_level: {log_level}, verbose: {verbose}")
    logger.debug(f"Remaining args for processing: {remaining_args}")
    
    # Find command in the remaining arguments
    command, command_index = find_command_in_args(remaining_args)
    
    subcommand_args = remaining_args[command_index:]
    
    # Route to appropriate command with extracted global state
    return route_command_with_globals(command, subcommand_args, verbose)


def route_command_with_globals(command: str, subcommand_args: list[str], verbose: bool) -> int:
    """Route commands to appropriate CLI classes with global argument context"""
    parser = create_main_parser()
    subparser_map = parser._subparser_map
    
    try:
        if command == 'clone':
            from clone import Clone
            Clone.cli_executor(subcommand_args, subparser=subparser_map['clone'])
        elif command == 'status':
            from status import Status
            Status.cli_executor(subcommand_args, subparser=subparser_map['status'])
        elif command == 'snapshot':
            from snapshot import Snapshot
            Snapshot.cli_executor(subcommand_args, subparser=subparser_map['snapshot'])
        elif command == 'setup':
            from setup import setup_environment
            setup_environment()
        else:
            print(f"Unknown command: {command}")
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
        if verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())