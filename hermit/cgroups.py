import os
import subprocess
from pathlib import Path

CGROUP_NAME = "hermit-sandbox"
CGROUP_PATH = Path(f"/sys/fs/cgroup/{CGROUP_NAME}")

def setup_cgroup(memory_max_mb: int = 512, cpu_quota_percent: int = 50, pids_max: int = 100):
    """Set up cgroup with resource limits.

    Args:
        memory_max_mb: Maximum memory in megabytes
        cpu_quota_percent: CPU quota as percentage (50 = 50% of one core)
        pids_max: Maximum number of processes
    """
    CGROUP_PATH.mkdir(exist_ok=True)

    parent_subtree = Path("/sys/fs/cgroup/cgroup.subtree_control")

    if parent_subtree.exists():
        parent_subtree.write_text("+cpu +memory +pids")

    # Memory limit (convert MB to bytes)
    memory_bytes = memory_max_mb * 1024 * 1024
    (CGROUP_PATH / "memory.max").write_text(str(memory_bytes))

    # Disable swap to enforce hard memory limit
    (CGROUP_PATH / "memory.swap.max").write_text("0")

    # CPU quota (percentage to microseconds per 100ms period)
    quota_us = cpu_quota_percent * 1000
    (CGROUP_PATH / "cpu.max").write_text(f"{quota_us} 100000")

    # PID limit
    (CGROUP_PATH / "pids.max").write_text(str(pids_max))

def add_process_to_cgroup(pid: int):
    (CGROUP_PATH / "cgroup.procs").write_text(str(pid))

def cleanup_cgroup():
    if CGROUP_PATH.exists():
        CGROUP_PATH.rmdir()

def get_current_usage() -> dict:
    """Get current resource usage stats."""
    return {
        "memory_bytes": int((CGROUP_PATH / "memory.current").read_text().strip()),
        "pids": int((CGROUP_PATH / "pids.current").read_text().strip()),
    }