import os
import subprocess
from pathlib import Path
from hermit.config import get_allowed_directories

SANDBOX_ROOT = "/home/ubuntu/sandbox-root"


def get_mount_list() -> list:
    """Get mount mappings from config, returns list of (host, sandbox) tuples."""
    dirs = get_allowed_directories()
    return [(d["host"], d["sandbox"]) for d in dirs]

def setup_mounts():
    mounted = []

    for host_path, sandbox_path in get_mount_list():
        host_full = os.path.expanduser(host_path)
        sandbox_full = f"{SANDBOX_ROOT}{sandbox_path}"

        if not os.path.exists(host_full):
            print(f"Skipping {host_path} (doesn't exist)")
            continue
        
        # create mount point in sandbox
        os.makedirs(sandbox_full, exist_ok=True)

        result = subprocess.run(
            ["mount","--bind", host_full, sandbox_full],
            capture_output=True
        )

        if result.returncode == 0:
            print(f"Mounted {host_path} → {sandbox_path}")
            mounted.append(sandbox_full)
        else:
            print(f"Failed to mount {host_path}")
    
    return mounted

def cleanup_mounts(mounted: list):
    for mount_point in mounted:
        subprocess.run(["umount", mount_point], capture_output=True)
        print(f"Unmounted {mount_point}")

def list_mounts():
    print("\nExposed folders:")
    for host_path, sandbox_path in get_mount_list():
        host_full = os.path.expanduser(host_path)
        #exists = "✅" if os.path.exists(host_full) else "❌"
        print(f"   {host_path} → {sandbox_path}")
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
