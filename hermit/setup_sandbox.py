#!/usr/bin/env python3
"""
Sandbox setup script for Hermit.

Creates the chroot environment with all required binaries and libraries.
Run with: sudo python -m hermit.setup_sandbox
"""

import os
import shutil
import subprocess
from pathlib import Path

SANDBOX_ROOT = Path("/home/ubuntu/sandbox-root")

# Binaries to include in the sandbox
REQUIRED_BINARIES = [
    # Shell
    "/bin/sh",
    "/bin/bash",

    # File operations
    "/bin/ls",
    "/bin/cat",
    "/bin/mkdir",
    "/bin/mv",
    "/bin/cp",
    "/bin/rm",
    "/usr/bin/touch",
    "/usr/bin/find",
    "/bin/chmod",
    "/bin/chown",

    # Text utilities
    "/usr/bin/head",
    "/usr/bin/tail",
    "/usr/bin/wc",
    "/bin/grep",
    "/usr/bin/sort",
    "/usr/bin/uniq",

    # Python
    "/usr/bin/python3",
]


def copy_python_stdlib(sandbox: Path):
    """Copy Python standard library."""
    src = Path("/usr/lib/python3.12")
    dest = sandbox / "usr/lib/python3.12"
    if src.exists() and not dest.exists():
        shutil.copytree(src, dest, dirs_exist_ok=True)
        print(f"  ✓ Python standard library")
    elif dest.exists():
        print(f"  · Python standard library (exists)")


def copy_pyseccomp(sandbox: Path):
    """Copy pyseccomp module and libseccomp."""
    # Find pyseccomp.py
    locations = [
        "/home/ubuntu/sandboxed-agent/venv/lib/python3.12/site-packages/pyseccomp.py",
        "/usr/lib/python3/dist-packages/pyseccomp.py",
    ]
    for src in locations:
        if os.path.exists(src):
            dest = sandbox / "usr/lib/python3.12/pyseccomp.py"
            shutil.copy2(src, dest)

            # Patch pyseccomp to use hardcoded path (ctypes.util.find_library doesn't work in chroot)
            content = dest.read_text()
            content = content.replace(
                '_libseccomp_path = ctypes.util.find_library("seccomp")',
                '_libseccomp_path = "/usr/lib/libseccomp.so.2"'
            )
            dest.write_text(content)
            print(f"  ✓ pyseccomp")
            break

    # Copy required libraries for pyseccomp
    libs = [
        "/lib/x86_64-linux-gnu/libseccomp.so.2",
        "/lib/x86_64-linux-gnu/libffi.so.8",
    ]
    for lib in libs:
        if os.path.exists(lib):
            dest = sandbox / lib.lstrip("/")
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copy2(lib, dest)
                print(f"  ✓ {Path(lib).name}")

    # Also copy libseccomp to /usr/lib for the hardcoded path
    libseccomp_src = "/lib/x86_64-linux-gnu/libseccomp.so.2"
    libseccomp_dest = sandbox / "usr/lib/libseccomp.so.2"
    if os.path.exists(libseccomp_src) and not libseccomp_dest.exists():
        libseccomp_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(libseccomp_src, libseccomp_dest)


def get_library_deps(binary: str) -> list:
    """Get shared library dependencies for a binary using ldd."""
    try:
        result = subprocess.run(
            ["ldd", binary],
            capture_output=True,
            text=True
        )
        libs = []
        for line in result.stdout.splitlines():
            # Parse lines like: libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x...)
            if "=>" in line and "not found" not in line:
                parts = line.split("=>")
                if len(parts) == 2:
                    lib_path = parts[1].strip().split()[0]
                    if lib_path.startswith("/"):
                        libs.append(lib_path)
            # Handle lines like: /lib64/ld-linux-x86-64.so.2 (0x...)
            elif line.strip().startswith("/"):
                lib_path = line.strip().split()[0]
                libs.append(lib_path)
        return libs
    except Exception as e:
        print(f"  Warning: Could not get deps for {binary}: {e}")
        return []


def copy_with_deps(binary: str, sandbox: Path):
    """Copy a binary and all its library dependencies to the sandbox."""
    if not os.path.exists(binary):
        print(f"  ✗ Not found: {binary}")
        return False

    # Copy the binary
    dest = sandbox / binary.lstrip("/")
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not dest.exists():
        shutil.copy2(binary, dest)
        os.chmod(dest, 0o755)
        print(f"  ✓ {binary}")
    else:
        print(f"  · {binary} (exists)")

    # Copy dependencies
    for lib in get_library_deps(binary):
        lib_dest = sandbox / lib.lstrip("/")
        if not lib_dest.exists():
            lib_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(lib, lib_dest)

    return True


def setup_directory_structure(sandbox: Path):
    """Create the basic directory structure."""
    dirs = [
        "bin", "sbin", "usr/bin", "usr/lib",
        "lib", "lib64", "lib/x86_64-linux-gnu",
        "etc", "dev", "tmp", "proc",
        "workspace", "sandbox",
    ]

    for d in dirs:
        (sandbox / d).mkdir(parents=True, exist_ok=True)

    # Set tmp permissions
    os.chmod(sandbox / "tmp", 0o1777)


def setup_etc_files(sandbox: Path):
    """Create minimal /etc files needed for operation."""
    etc = sandbox / "etc"

    # passwd - minimal
    (etc / "passwd").write_text("root:x:0:0:root:/root:/bin/sh\nnobody:x:65534:65534:nobody:/:/bin/false\n")

    # group - minimal
    (etc / "group").write_text("root:x:0:\nnogroup:x:65534:\n")

    # nsswitch.conf - use files only
    (etc / "nsswitch.conf").write_text("passwd: files\ngroup: files\nhosts: files\n")


def setup_dev_nodes(sandbox: Path):
    """Create basic device nodes (requires root)."""
    dev = sandbox / "dev"

    nodes = [
        ("null", 0o666, 1, 3),
        ("zero", 0o666, 1, 5),
        ("random", 0o666, 1, 8),
        ("urandom", 0o666, 1, 9),
    ]

    for name, mode, major, minor in nodes:
        node_path = dev / name
        if not node_path.exists():
            try:
                os.mknod(node_path, mode | 0o020000, os.makedev(major, minor))
                print(f"  ✓ /dev/{name}")
            except PermissionError:
                print(f"  ✗ /dev/{name} (need root)")
            except FileExistsError:
                pass


def copy_sandbox_scripts(sandbox: Path):
    """Copy the sandbox wrapper scripts."""
    src_dir = Path(__file__).parent

    # Copy sandbox_wrapper.py
    wrapper_src = src_dir / "sandbox_wrapper.py"
    if wrapper_src.exists():
        dest = sandbox / "sandbox" / "sandbox_wrapper.py"
        shutil.copy2(wrapper_src, dest)
        print(f"  ✓ sandbox_wrapper.py")

    # Copy seccomp_filter.py
    seccomp_src = src_dir / "seccomp_filter.py"
    if seccomp_src.exists():
        dest = sandbox / "sandbox" / "seccomp_filter.py"
        shutil.copy2(seccomp_src, dest)
        print(f"  ✓ seccomp_filter.py")


def create_python_symlink(sandbox: Path):
    """Create python -> python3 symlink."""
    python_link = sandbox / "usr/bin/python"
    if not python_link.exists():
        python_link.symlink_to("/usr/bin/python3")
        print(f"  ✓ python -> python3 symlink")


def run_step(message: str, func, *args):
    """Run a setup step with spinner animation."""
    from hermit import ui
    import io
    import sys

    spinner = ui.Spinner(message)
    spinner.start()

    # Suppress prints during execution
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        result = func(*args)
        sys.stdout = old_stdout
        spinner.stop()
        print(f"  {ui.green(ui.CHECK)} {message}")
        return result
    except Exception as e:
        sys.stdout = old_stdout
        spinner.stop()
        print(f"  {ui.red(ui.CROSS)} {message}: {e}")
        raise


def main():
    from hermit import ui

    print(f"""
  {ui.bold('Setting up Hermit sandbox')}
  {ui.dim(f'Location: {SANDBOX_ROOT}')}
""")

    # Check if running as root
    if os.geteuid() != 0:
        print(f"  {ui.yellow(ui.WARN)} Not running as root — some steps may fail\n")

    # Run setup steps with spinners
    run_step("Creating directories", setup_directory_structure, SANDBOX_ROOT)

    # Binaries need special handling for the count
    from hermit import ui
    import io
    import sys

    spinner = ui.Spinner("Copying binaries")
    spinner.start()
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        for binary in REQUIRED_BINARIES:
            copy_with_deps(binary, SANDBOX_ROOT)
    finally:
        sys.stdout = old_stdout
        spinner.stop()
    print(f"  {ui.green(ui.CHECK)} Copied {len(REQUIRED_BINARIES)} binaries")

    run_step("Copying Python stdlib", copy_python_stdlib, SANDBOX_ROOT)
    run_step("Copying pyseccomp", copy_pyseccomp, SANDBOX_ROOT)
    run_step("Creating symlinks", create_python_symlink, SANDBOX_ROOT)
    run_step("Setting up /etc", setup_etc_files, SANDBOX_ROOT)
    run_step("Creating /dev nodes", setup_dev_nodes, SANDBOX_ROOT)
    run_step("Copying sandbox scripts", copy_sandbox_scripts, SANDBOX_ROOT)

    print(f"""
  {ui.green(ui.CHECK)} {ui.bold('Sandbox ready!')}
""")


if __name__ == "__main__":
    main()
