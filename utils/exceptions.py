"""Custom exceptions for SPAM (Scripting Proxmox Automation Magic)"""

from typing import Optional


class SpamError(Exception):
    """Base exception for all SPAM-related errors"""
    
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ProxmoxConnectionError(SpamError):
    """Raised when connection to Proxmox fails"""
    pass


class ProxmoxAPIError(SpamError):
    """Raised when Proxmox API operations fail"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[str] = None):
        super().__init__(message, details)
        self.status_code = status_code


class VMNotFoundError(SpamError):
    """Raised when specified VM cannot be found"""
    
    def __init__(self, vmid: str, node: Optional[str] = None):
        if node:
            message = f"VM {vmid} not found on node {node}"
        else:
            message = f"VM {vmid} not found in cluster"
        super().__init__(message)
        self.vmid = vmid
        self.node = node


class NodeNotFoundError(SpamError):
    """Raised when specified node cannot be found"""
    
    def __init__(self, node: str):
        super().__init__(f"Node {node} not found in cluster")
        self.node = node


class ConfigurationError(SpamError):
    """Raised when configuration is invalid or missing"""
    pass


class ValidationError(SpamError):
    """Raised when input validation fails"""
    pass


class SnapshotError(SpamError):
    """Raised when snapshot operations fail"""
    pass


class CloneError(SpamError):
    """Raised when VM cloning operations fail"""
    pass


class TaskTimeoutError(SpamError):
    """Raised when Proxmox task times out"""
    
    def __init__(self, task_id: str, timeout: int):
        super().__init__(f"Task {task_id} timed out after {timeout} seconds")
        self.task_id = task_id
        self.timeout = timeout


class EnvironmentFileError(ConfigurationError):
    """Raised when environment file cannot be loaded or is invalid"""
    pass