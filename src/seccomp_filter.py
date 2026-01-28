import pyseccomp as seccomp

def create_filter():
    """
    
    Create a seccomp filter that allows only safe syscalls.
    Default: KILL the process if it tries a blocked syscall.
    
    """

    # Start with "kill on any syscall" then whitelist safe ones
    f = seccomp.SyscallFilter(defaction=seccomp.KILL)

    # File operations (safe)
    f.add_rule(seccomp.ALLOW, "read")
    f.add_rule(seccomp.ALLOW, "write")
    f.add_rule(seccomp.ALLOW, "open")
    f.add_rule(seccomp.ALLOW, "openat")
    f.add_rule(seccomp.ALLOW, "close")
    f.add_rule(seccomp.ALLOW, "stat")
    f.add_rule(seccomp.ALLOW, "fstat")
    f.add_rule(seccomp.ALLOW, "lstat")
    f.add_rule(seccomp.ALLOW, "lseek")
    f.add_rule(seccomp.ALLOW, "getdents64")
    f.add_rule(seccomp.ALLOW, "getdents")
    
    # Memory (needed for basic operation)
    f.add_rule(seccomp.ALLOW, "mmap")
    f.add_rule(seccomp.ALLOW, "mprotect")
    f.add_rule(seccomp.ALLOW, "munmap")
    f.add_rule(seccomp.ALLOW, "brk")
    
    # Process basics
    f.add_rule(seccomp.ALLOW, "exit")
    f.add_rule(seccomp.ALLOW, "exit_group")
    f.add_rule(seccomp.ALLOW, "execve")
    f.add_rule(seccomp.ALLOW, "fork")
    f.add_rule(seccomp.ALLOW, "vfork")
    f.add_rule(seccomp.ALLOW, "clone")
    f.add_rule(seccomp.ALLOW, "clone3")
    f.add_rule(seccomp.ALLOW, "wait4")
    f.add_rule(seccomp.ALLOW, "getpid")
    f.add_rule(seccomp.ALLOW, "getuid")
    f.add_rule(seccomp.ALLOW, "geteuid")
    f.add_rule(seccomp.ALLOW, "getgid")
    f.add_rule(seccomp.ALLOW, "getegid")
    
    # Misc needed for shell
    f.add_rule(seccomp.ALLOW, "access")
    f.add_rule(seccomp.ALLOW, "faccessat")
    f.add_rule(seccomp.ALLOW, "faccessat2")
    f.add_rule(seccomp.ALLOW, "pipe")
    f.add_rule(seccomp.ALLOW, "pipe2")
    f.add_rule(seccomp.ALLOW, "dup")
    f.add_rule(seccomp.ALLOW, "dup2")
    f.add_rule(seccomp.ALLOW, "dup3")
    f.add_rule(seccomp.ALLOW, "fcntl")
    f.add_rule(seccomp.ALLOW, "ioctl")
    f.add_rule(seccomp.ALLOW, "getcwd")
    f.add_rule(seccomp.ALLOW, "chdir")
    f.add_rule(seccomp.ALLOW, "readlink")
    f.add_rule(seccomp.ALLOW, "readlinkat")
    f.add_rule(seccomp.ALLOW, "uname")
    f.add_rule(seccomp.ALLOW, "arch_prctl")
    f.add_rule(seccomp.ALLOW, "set_tid_address")
    f.add_rule(seccomp.ALLOW, "set_robust_list")
    f.add_rule(seccomp.ALLOW, "rseq")
    f.add_rule(seccomp.ALLOW, "prlimit64")
    f.add_rule(seccomp.ALLOW, "getrandom")
    f.add_rule(seccomp.ALLOW, "newfstatat")
    f.add_rule(seccomp.ALLOW, "statx")

    # BLOCKED (not in whitelist):
    # - reboot
    # - mount/umount
    # - ptrace
    # - kexec_load
    # - init_module / delete_module
    # - sethostname
    # - setdomainname
    # - socket/connect/bind (no network!)

    return f

if __name__ == "__main__":
    import os
    
    print("Before seccomp: I can do anything")
    print(f"  PID: {os.getpid()}")
    
    # Load the filter
    f = create_filter()
    f.load()
    
    print("After seccomp: I'm restricted")
    print(f"  PID: {os.getpid()}")  # This still works (getpid is allowed)
    
    # This would kill the process (socket is not allowed):
    # import socket
    # s = socket.socket()  # KILLED!
    
    print("Try to import socket and create one - process will be killed")


"""
How to integrate into agent? seccomp applies to the current process, so we need to apply it in the child process that runs inside the sandbox 

Create a wrapper script that runs inside the sandbox and applies seccomp before executing the command.

"""