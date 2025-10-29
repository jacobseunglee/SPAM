"""Utility functions for SPAM (Scripting Proxmox Automation Magic)"""

import time
from typing import Callable, Any, Optional, Union
from functools import wraps

from proxmoxer import ProxmoxAPI
from utils.exceptions import TaskTimeoutError, ProxmoxAPIError, VMNotFoundError
from utils.validation import validate_vmid, validate_node_name


# We'll create a simple logger fallback if logging_config isn't available
try:
    from utils.logging_config import get_utils_logger
    logger = get_utils_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry function calls on failure

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay between retries
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay} seconds..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")

            if last_exception is not None:
                raise last_exception
            else:
                raise RuntimeError(
                    f"All {max_attempts} attempts failed for {func.__name__}, but no exception was caught. "
                    "Check the 'exceptions' argument to the retry_on_failure decorator."
                )
        return wrapper
    return decorator


@retry_on_failure(max_attempts=3, delay=2.0, exceptions=(ProxmoxAPIError, Exception))
def block_until_done(
    prox: ProxmoxAPI,
    task_id: str,
    node: str,
    timeout: int = 300,
    poll_interval: float = 2.0
) -> dict:
    """
    Block until a Proxmox task is completed

    Args:
        prox: ProxmoxAPI instance
        task_id: Task ID to monitor
        node: Node where the task is running
        timeout: Maximum time to wait in seconds
        poll_interval: Time between status checks in seconds

    Returns:
        Final task status dictionary

    Raises:
        TaskTimeoutError: If task doesn't complete within timeout
        ProxmoxAPIError: If task fails or API error occurs
    """
    node = validate_node_name(node)
    start_time = time.time()

    logger.debug(f"Monitoring task {task_id} on node {node}")

    while True:
        try:
            data = prox.nodes(node).tasks(task_id).status.get()
        except Exception as e:
            raise ProxmoxAPIError(f"Failed to get task status: {e}")

        status = data.get("status", "")

        if status == "stopped":
            # Check if task completed successfully
            exitstatus = data.get("exitstatus")
            if exitstatus and exitstatus != "OK":
                raise ProxmoxAPIError(
                    f"Task {task_id} failed with status: {exitstatus}",
                    details=data.get("stderr", "No error details available")
                )

            logger.debug(f"Task {task_id} completed successfully")
            return data

        # Check timeout
        if time.time() - start_time > timeout:
            raise TaskTimeoutError(task_id, timeout)

        time.sleep(poll_interval)


def function_over_range(
    func: Callable,
    first: int,
    last: int,
    *args,
    fail_fast: bool = False,
    **kwargs
) -> list[tuple[int, bool, Optional[Exception]]]:
    """
    Execute a function over a range of VM IDs

    Args:
        func: Function to execute (must accept vmid as parameter)
        first: First VM ID in range
        last: Last VM ID in range (inclusive)
        *args: Positional arguments to pass to function
        fail_fast: If True, stop on first error
        **kwargs: Keyword arguments to pass to function

    Returns:
        List of tuples: (vmid, success, exception)
    """
    first = validate_vmid(first)
    last = validate_vmid(last)

    if first > last:
        raise ValueError(f"First VM ID ({first}) cannot be greater than last ({last})")

    results = []
    logger.info(f"Executing {func.__name__} over range {first}-{last}")

    for vmid in range(first, last + 1):
        try:
            func(*args, **kwargs, vmid=vmid)
            results.append((vmid, True, None))
            logger.debug(f"Successfully executed {func.__name__} for VM {vmid}")
        except Exception as e:
            results.append((vmid, False, e))
            logger.error(f"Failed to execute {func.__name__} for VM {vmid}: {e}")

            if fail_fast:
                logger.error("Stopping execution due to fail_fast=True")
                break

    # Summary
    successful = sum(1 for _, success, _ in results if success)
    total = len(results)
    logger.info(f"Range execution complete: {successful}/{total} successful")

    return results


def get_vm_node(prox: ProxmoxAPI, vmid: Union[str, int]) -> str:
    """
    Get the node where a VM is located

    Args:
        prox: ProxmoxAPI instance
        vmid: VM ID to search for

    Returns:
        Node name where the VM is located

    Raises:
        VMNotFoundError: If VM is not found in the cluster
        ProxmoxAPIError: If API call fails
    """
    vmid = validate_vmid(vmid)

    try:
        vms = prox.cluster.resources.get(type="vm")
    except Exception as e:
        raise ProxmoxAPIError(f"Failed to get cluster resources: {e}")

    for vm in vms:
        if str(vm.get("vmid")) == str(vmid):
            node = vm.get("node")
            if node:
                logger.debug(f"Found VM {vmid} on node {node}")
                return node

    raise VMNotFoundError(str(vmid))


def get_vm_config(prox: ProxmoxAPI, vmid: Union[str, int], node: Optional[str] = None) -> dict:
    """
    Get VM configuration

    Args:
        prox: ProxmoxAPI instance
        vmid: VM ID
        node: Node name (will be auto-detected if not provided)

    Returns:
        VM configuration dictionary

    Raises:
        VMNotFoundError: If VM is not found
        ProxmoxAPIError: If API call fails
    """
    vmid = validate_vmid(vmid)

    if not node:
        node = get_vm_node(prox, vmid)
    else:
        node = validate_node_name(node)

    try:
        config = prox.nodes(node).qemu(vmid).config.get()
        logger.debug(f"Retrieved config for VM {vmid} on node {node}")
        return config
    except Exception as e:
        raise ProxmoxAPIError(f"Failed to get VM {vmid} config: {e}")


def wait_for_vm_status(
    prox: ProxmoxAPI,
    vmid: Union[str, int],
    expected_status: str,
    node: Optional[str] = None,
    timeout: int = 120,
    poll_interval: float = 5.0
) -> bool:
    """
    Wait for VM to reach expected status

    Args:
        prox: ProxmoxAPI instance
        vmid: VM ID
        expected_status: Expected VM status ('running', 'stopped', etc.)
        node: Node name (will be auto-detected if not provided)
        timeout: Maximum wait time in seconds
        poll_interval: Time between checks in seconds

    Returns:
        True if VM reaches expected status within timeout

    Raises:
        VMNotFoundError: If VM is not found
        ProxmoxAPIError: If API call fails
    """
    vmid = validate_vmid(vmid)

    if not node:
        node = get_vm_node(prox, vmid)
    else:
        node = validate_node_name(node)

    start_time = time.time()
    logger.debug(f"Waiting for VM {vmid} to reach status '{expected_status}'")

    while time.time() - start_time < timeout:
        try:
            status = prox.nodes(node).qemu(vmid).status.current.get()
            current_status = status.get('status', 'unknown')

            if current_status == expected_status:
                logger.debug(f"VM {vmid} reached expected status '{expected_status}'")
                return True

        except Exception as e:
            logger.warning(f"Error checking VM {vmid} status: {e}")

        time.sleep(poll_interval)

    logger.warning(f"VM {vmid} did not reach status '{expected_status}' within {timeout} seconds")
    return False
