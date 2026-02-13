import os
import subprocess
from pathlib import Path
from hermit.config import get_allowed_directories
from hermit import ui

SANDBOX_ROOT = "/home/ubuntu/sandbox-root"


def get_mount_list() -> list:
    """Get mount mappings from config, returns list of (host, sandbox) tuples."""
    dirs = get_allowed_directories()
    return [(d["host"], d["sandbox"]) for d in dirs]


def setup_mounts():
    """Mount configured directories into the sandbox."""
    mounted = []

    for host_path, sandbox_path in get_mount_list():
        host_full = os.path.expanduser(host_path)
        sandbox_full = f"{SANDBOX_ROOT}{sandbox_path}"

        if not os.path.exists(host_full):
            ui.mount_status(host_path, sandbox_path, False)
            continue

        # create mount point in sandbox
        os.makedirs(sandbox_full, exist_ok=True)

        result = subprocess.run(
            ["mount", "--bind", host_full, sandbox_full],
            capture_output=True
        )

        if result.returncode == 0:
            ui.mount_status(host_path, sandbox_path, True)
            mounted.append(sandbox_full)
        else:
            ui.mount_status(host_path, sandbox_path, False)

    return mounted


def cleanup_mounts(mounted: list):
    """Unmount all mounted directories."""
    for mount_point in mounted:
        subprocess.run(["umount", mount_point], capture_output=True)


def mount_dr(host_path: str, sandbox_path: str) -> str | None:
    """Mount a single directory into the sandbox. Returns sandbox fullpath or None."""
    host_full = os.path.expanduser(host_path)
    sandbox_full = f"{SANDBOX_ROOT}{sandbox_path}"

    if not os.path.exists(host_full):
        ui.mount_status(host_path, sandbox_path, False)
        return None

    os.makedirs(sandbox_full, exist_ok=True)
    res = subprocess.run(
        ["mount", "--bind", host_full, sandbox_full],
        capture_output=True
    )

    if res.returncode == 0:
        ui.mount_status(host_path, sandbox_path, True)
        return sandbox_full
    else:
        ui.mount_status(host_path, sandbox_path, False)
        return None

def unmount_dr(sandbox_path: str) -> bool:
    sandbox_full = f"{SANDBOX_ROOT}{sandbox_path}"
    res = subprocess.run(
        ["umount", sandbox_full], 
        capture_output=True
    )
    return res.returncode == 0

def list_mounts(active_mounts: list):
    """Show configured directories and their live mount status."""
    print()
    for host_path, sandbox_path in get_mount_list():
        sandbox_full = f"{SANDBOX_ROOT}{sandbox_path}"
        is_mounted = sandbox_full in active_mounts
        status = ui.green("mounted") if is_mounted else ui.dim("not mounted")
        print(f"   {host_path} → {sandbox_path}  [{status}]")
    print()
                
if __name__ == "__main__":
    print("Testing mount setup...\n")
    
    # Create test folders if needed
    os.makedirs(os.path.expanduser("~/Downloads"), exist_ok=True)
    os.makedirs(os.path.expanduser("~/projects"), exist_ok=True)
    
    # Create a test file
    test_file = os.path.expanduser("~/Downloads/test_from_host.txt")
    with open(test_file, "w") as f:
        f.write("Hello from host!")
    
    list_mounts()
    
    mounted = setup_mounts()
    
    print("\n📁 Inside sandbox /workspace:")
    sandbox_workspace = f"{SANDBOX_ROOT}/workspace"
    if os.path.exists(sandbox_workspace):
        for item in os.listdir(sandbox_workspace):
            print(f"   {item}/")
    
    input("\nPress Enter to cleanup...")
    cleanup_mounts(mounted)
