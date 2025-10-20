from proxmoxer import ProxmoxAPI
from time import sleep

def block_until_done(prox: ProxmoxAPI, task_id: str, node: str, display: bool = False) -> None:
    start = 0
    data = {"status": ""}
    while (data["status"] != "stopped"):
        data = prox.nodes(node).tasks(task_id).status.get()
        if display:
            log = prox.nodes(node).tasks(task_id).log.get(start=start)
            for line in log:
                print(line['t'])
            start += len(log)
        sleep(0.1)
    return

def function_over_range(func: callable, first: int, last: int, *args, **kwargs):
    for vmid in range(first, last + 1):
        func(*args, **kwargs, vmid=vmid)
    return
