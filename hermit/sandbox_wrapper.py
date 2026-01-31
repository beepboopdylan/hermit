#!/usr/bin/env python3

"""
This script runs INSIDE the sandbox.
It applies seccomp filters, then executes the command.
"""

import sys
import os
import errno

# Set library path before importing pyseccomp (ctypes.util.find_library needs this)
os.environ["LD_LIBRARY_PATH"] = "/usr/lib:/lib/x86_64-linux-gnu"
import pyseccomp as seccomp

def setup_seccomp():
    """
    Create a seccomp filter that blocks dangerous syscalls.
    Default: ALLOW - permit most syscalls
    Blacklist: Block dangerous operations
    """

    # Start permissive, then block dangerous syscalls
    f = seccomp.SyscallFilter(seccomp.ALLOW)

    # KILL: Truly dangerous syscalls - terminate process immediately
    kill_syscalls = [
        # System destruction
        "reboot",
        "kexec_load",
        "kexec_file_load",

        # Kernel modules
        "init_module",
        "finit_module",
        "delete_module",

        # Filesystem manipulation
        "mount",
        "umount",
        "umount2",
        "pivot_root",
        "chroot",

        # Debugging/tracing (could escape sandbox)
        "ptrace",
        "process_vm_readv",
        "process_vm_writev",

        # System configuration
        "sethostname",
        "setdomainname",
        "settimeofday",
        "adjtimex",
        "clock_adjtime",
    ]

    # ERRNO: Network syscalls - return EPERM so programs handle gracefully
    # (glibc NSS may probe for network even when using local files)
    errno_syscalls = [
        "socket",
        "connect",
        "bind",
        "listen",
        "accept",
        "accept4",
        "sendto",
        "recvfrom",
        "sendmsg",
        "recvmsg",
    ]

    for syscall in kill_syscalls:
        try:
            f.add_rule(seccomp.KILL, syscall)
        except Exception:
            pass

    for syscall in errno_syscalls:
        try:
            f.add_rule(seccomp.ERRNO(errno.EPERM), syscall)
        except Exception:
            pass

    f.load()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: sandbox_wrapper.py <command>", file=sys.stderr)
        sys.exit(1)
    
    command = " ".join(sys.argv[1:])
    
    # Apply seccomp BEFORE running command
    setup_seccomp()
    
    # Execute the command via bash (for brace expansion support)
    os.execvp("/bin/bash", ["/bin/bash", "-c", f"export LC_ALL=C LANG=C; {command}"])

