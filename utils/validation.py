"""Input validation utilities for SPAM"""

import ipaddress
import re
from typing import Union, List, Optional
from utils.exceptions import ValidationError


def validate_vmid(vmid: Union[str, int]) -> int:
    """
    Validate VM ID
    
    Args:
        vmid: VM ID to validate
        
    Returns:
        Validated VM ID as integer
        
    Raises:
        ValidationError: If VM ID is invalid
    """
    try:
        vmid_int = int(vmid)
        if vmid_int < 100 or vmid_int > 999999999:
            raise ValidationError(f"VM ID must be between 100 and 999999999, got {vmid_int}")
        return vmid_int
    except (ValueError, TypeError):
        raise ValidationError(f"VM ID must be a valid integer, got {vmid}")


def validate_node_name(node: str) -> str:
    """
    Validate Proxmox node name
    
    Args:
        node: Node name to validate
        
    Returns:
        Validated node name
        
    Raises:
        ValidationError: If node name is invalid
    """
    if not node or not isinstance(node, str):
        raise ValidationError("Node name cannot be empty")
    
    # Proxmox node names should follow hostname conventions
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$', node):
        raise ValidationError(f"Invalid node name format: {node}")
    
    return node.strip()


def validate_ip_address(ip: str) -> str:
    """
    Validate IP address format
    
    Args:
        ip: IP address to validate
        
    Returns:
        Validated IP address
        
    Raises:
        ValidationError: If IP address is invalid
    """
    if not ip:
        raise ValidationError("IP address cannot be empty")
    
    try:
        # Use ipaddress module for comprehensive IPv4 and IPv6 validation
        # This supports all valid formats including compressed notation (::),
        # mixed notation (::ffff:192.0.2.1), and other valid IPv6 formats
        ipaddress.ip_address(ip)
        return ip
    except ValueError as e:
        raise ValidationError(f"Invalid IP address format: {ip}")


def validate_vmid_range(range_values: List[Union[str, int]]) -> tuple[int, int]:
    """
    Validate VM ID range
    
    Args:
        range_values: List containing start and end VM IDs
        
    Returns:
        Tuple of (start_vmid, end_vmid)
        
    Raises:
        ValidationError: If range is invalid
    """
    if not range_values or len(range_values) != 2:
        raise ValidationError("Range must contain exactly two values")
    
    try:
        start_vmid = validate_vmid(range_values[0])
        end_vmid = validate_vmid(range_values[1])
    except ValidationError as e:
        raise ValidationError(f"Invalid range values: {e}")
    
    if start_vmid >= end_vmid:
        raise ValidationError(f"Start VM ID ({start_vmid}) must be less than end VM ID ({end_vmid})")
    
    if end_vmid - start_vmid > 1000:
        raise ValidationError(f"Range too large: {end_vmid - start_vmid} VMs (maximum 1000)")
    
    return start_vmid, end_vmid


def validate_snapshot_name(snapname: str) -> str:
    """
    Validate snapshot name
    
    Args:
        snapname: Snapshot name to validate
        
    Returns:
        Validated snapshot name
        
    Raises:
        ValidationError: If snapshot name is invalid
    """
    if not snapname:
        raise ValidationError("Snapshot name cannot be empty")
    
    # Proxmox snapshot names should be alphanumeric with limited special chars
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-_.]{0,39}$', snapname):
        raise ValidationError(f"Invalid snapshot name: {snapname}")
    
    return snapname.strip()


def validate_vm_name(name: str) -> str:
    """
    Validate VM name
    
    Args:
        name: VM name to validate
        
    Returns:
        Validated VM name
        
    Raises:
        ValidationError: If VM name is invalid
    """
    if not name:
        raise ValidationError("VM name cannot be empty")
    
    # VM names should be reasonable length and character set
    if len(name) > 64:
        raise ValidationError(f"VM name too long (max 64 characters): {name}")
    
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-_.]{0,63}$', name):
        raise ValidationError(f"Invalid VM name format: {name}")
    
    return name.strip()


def validate_positive_integer(value: Union[str, int], name: str = "value") -> int:
    """
    Validate positive integer
    
    Args:
        value: Value to validate
        name: Name of the value for error messages
        
    Returns:
        Validated positive integer
        
    Raises:
        ValidationError: If value is not a positive integer
    """
    try:
        int_value = int(value)
        if int_value <= 0:
            raise ValidationError(f"{name} must be a positive integer, got {int_value}")
        return int_value
    except (ValueError, TypeError):
        raise ValidationError(f"{name} must be a valid integer, got {value}")


def validate_required_string(value: Optional[str], name: str) -> str:
    """
    Validate required string field
    
    Args:
        value: String value to validate
        name: Name of the field for error messages
        
    Returns:
        Validated string
        
    Raises:
        ValidationError: If string is empty or None
    """
    if not value or not value.strip():
        raise ValidationError(f"{name} is required and cannot be empty")
    
    return value.strip()