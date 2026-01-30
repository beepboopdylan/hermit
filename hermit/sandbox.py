import os
import subprocess

def run_in_namespace(command: str) -> str:
    """Run a command inside a Linux namespace (isolated)."""
    
    # unshare creates new namespaces
    # --mount: separate filesystem view
    # --pid: separate process view  
    # --fork: required for pid namespace
    # --mount-proc: mount /proc for the new pid namespace

    full_commands = [
        "unshare",
        "--mount",
        "--pid",
        "--fork",
        "--mount-proc",
        "sh", "-c", command
    ]

    res = subprocess.run(
        full_commands,
        capture_output=True,
        text=True
    )

    return res.stdout + res.stderr

if __name__ == "__main__":
    # Test it
    print("Outside namespace - all processes:")
    print(subprocess.run("ps aux | head -5", shell=True, capture_output=True, text=True).stdout)
    
    print("\nInside namespace - isolated processes:")
    print(run_in_namespace("ps aux"))
