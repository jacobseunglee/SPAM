# SPAM - Scripting Proxmox Automation Magic

A powerful command-line tool for automating Proxmox Virtual Environment (PVE) operations including VM cloning, status management, and snapshot operations.

## Features

- **VM Cloning**: Clone VMs individually or in bulk using configuration files
- **Status Management**: Start, stop, and destroy VMs across nodes
- **Snapshot Operations**: Create, rollback, and delete VM snapshots
- **Environment-based Deployments**: Deploy entire environments from YAML configurations
- **Cross-node Operations**: Manage VMs across multiple Proxmox nodes
- **Workshop/Training Support**: Specialized modes for educational environments

## Installation

1. Clone this repository:
```bash
git clone https://github.com/jacobseunglee/SPAM.git
cd SPAM
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment:
```bash
python main.py setup
```

## Configuration

### Environment Variables

Create a `.env` file or set the following environment variables:

```bash
PROXMOX_HOST=192.168.1.100
PROXMOX_USER=root
PROXMOX_PASSWORD=your_password
PROXMOX_REALM=pve
PROXMOX_DEFAULT_NODE=pve01
CONFIG_PATH=conf/env.yaml
SPAM_LOG_LEVEL=INFO
```

### Configuration Files

Create YAML configuration files in the `conf/` directory for environment-based operations:

```yaml
env:
  template_node: pve01
  nodes:
    - pve02
    - pve03
  boxes:
    - id: '1000'
      config:
        name: web-server
        newid: 2000
        full: 1
      cloud:
        ipconfig0: ip=192.168.1.10/24,gw=192.168.1.1
        nameserver: 8.8.8.8
```

## Usage

### Basic Commands

```bash
# Clone a single VM
python main.py clone 1000 2000 --node pve01 --name "new-vm"

# Start/stop VMs
python main.py status --start --node pve01 --vmid 1000
python main.py status --stop --range 1000 1010

# Create snapshots
python main.py snapshot --node pve01 --vmid 1000 --snapname "pre-update"

# Rollback to snapshot
python main.py snapshot --rollback --node pve01 --vmid 1000 --snapname "pre-update"
```

### Environment-based Operations

```bash
# Clone entire environment from config file
python main.py clone --environment conf/env.yaml

# Training/workshop modes
python main.py clone --workshop
python main.py clone --ccdctraining conf/training.yaml
```

### Advanced Features

```bash
# Cross-node operations for training environments
python main.py status --start --crossnode

# VM operations with ranges
python main.py status --destroy --range 1000 1020

# Snapshot with VM state
python main.py snapshot --vmstate --node pve01 --vmid 1000
```

## Architecture

SPAM uses a modular CLI architecture with the following components:

- **`main.py`**: Entry point and command routing
- **`cli.py`**: Base CLI class with common functionality
- **`clone.py`**: VM cloning operations
- **`status.py`**: VM status management (start/stop/destroy)
- **`snapshot.py`**: Snapshot operations
- **`conf/config.py`**: Configuration management
- **`utils/`**: Utility modules for validation, logging, and exceptions

## Error Handling

SPAM includes comprehensive error handling:

- Custom exception classes for different error types
- Retry mechanisms for Proxmox API operations
- Detailed logging with configurable levels
- Input validation for all parameters

## Logging

Logs are written to `~/.spam/logs/spam.log` by default. Configure logging with:

```bash
export SPAM_LOG_LEVEL=DEBUG
export SPAM_LOG_FILE=/path/to/custom/log
```

## Development

### Project Structure

```
SPAM/
├── main.py              # Entry point
├── cli.py               # Base CLI class
├── clone.py             # Clone operations
├── status.py            # Status operations
├── snapshot.py          # Snapshot operations
├── setup.py             # Environment setup
├── arguments/
│   └── options.py       # Argument parsing utilities
├── conf/
│   ├── config.py        # Configuration management
│   ├── env.yaml         # Default environment config
│   └── training.yaml    # Training environment config
└── utils/
    ├── cloudinit.py     # Cloud-init operations
    ├── exceptions.py    # Custom exceptions
    ├── logging_config.py # Logging configuration
    ├── utils.py         # Utility functions
    └── validation.py    # Input validation
```

### Contributing

1. Follow the existing code structure and patterns
2. Add proper type hints and documentation
3. Include error handling and validation
4. Write tests for new functionality
5. Update this README for new features

## Examples

### Example .env file:

```bash
PROXMOX_HOST=192.168.1.100
PROXMOX_USER=admin
PROXMOX_PASSWORD=secretpassword
PROXMOX_REALM=pve
PROXMOX_DEFAULT_NODE=pve01
```

### Example environment configuration:

```yaml
env:
  template_node: pve01
  nodes:
    - pve02
    - pve03
  boxes:
    - id: '9000'
      config:
        name: firewall
        newid: 1001
        full: 1
      cloud:
        ipconfig0: ip=10.0.1.1/24,gw=10.0.1.254
        nameserver: 8.8.8.8
    - id: '9001'
      config:
        name: webserver
        newid: 1002
        full: 1
      cloud:
        ipconfig0: ip=10.0.1.10/24,gw=10.0.1.1
        nameserver: 10.0.1.1
```

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please create an issue on the GitHub repository.


