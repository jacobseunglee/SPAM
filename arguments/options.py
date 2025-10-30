import argparse


def create_base_parser(prog: str, usage: str = "", desc=None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        usage=usage,
        description=desc,
        exit_on_error=False  # This prevents sys.exit() on error
    )
    add_verbosity_options(parser)
    return parser


def add_verbosity_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '-v', '--verbose', 
        action='store_true',
        help='Enable verbose output'
    )

def add_environment_file_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '-e', '--environment',
        type=str,
        nargs='?',
        const='conf/env.yaml',
        help='Specify and use configuration file to define targets for running the scripts against. Default file is conf/env.yaml'
    )  

def add_node_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        'node',
        nargs='?',
        type=str,
        help='Name of target node.'
    )
def add_optional_node_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '-o', '--node',
        nargs='?',
        type=str,
        help='Name of target node. Replace your default node set in environment variable'
    )
def add_vmid_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        'vmid',
        nargs='?',
        type=int,
        help='ID of source VM.'
    )
def add_newid_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        'newid',
        nargs='?',
        type=int,
        help='ID of target VM that will be created. Optional if -e is set.'
    )
def add_name_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '-n', '--name',
        type=str,
        help='Set a name for the new VM.'
    )
def add_pool_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '-p', '--pool',
        type=str,
        help='Add the new VM to the specified pool.'
    )
def add_target_node_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '-t', '--target',
        type=str,
        help='Target node. Only allowed if the original VM is on shared storage.'
    )
def add_range_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
            '-r', '--range',
            nargs=2,
            metavar=('first', 'last'),
            type=int,
            help='Range of VMIDs to modify (inclusive).'
    )