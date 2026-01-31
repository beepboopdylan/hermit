"""UI helpers for hermit - Claude-inspired minimal aesthetic."""

import sys
import time
import threading

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    ORANGE = "\033[38;5;208m"
    GREEN = "\033[38;5;114m"
    RED = "\033[38;5;203m"
    YELLOW = "\033[38;5;221m"
    GRAY = "\033[38;5;245m"
    WHITE = "\033[38;5;255m"


# Symbols
CHECK = "✓"
CROSS = "✗"
DOT = "●"
WARN = "⚠"
ARROW = "→"
PROMPT = ">"

# Spinner frames
SPINNER_FRAMES = ["◐", "◓", "◑", "◒"]


def orange(text: str) -> str:
    return f"{Colors.ORANGE}{text}{Colors.RESET}"

def green(text: str) -> str:
    return f"{Colors.GREEN}{text}{Colors.RESET}"

def red(text: str) -> str:
    return f"{Colors.RED}{text}{Colors.RESET}"

def yellow(text: str) -> str:
    return f"{Colors.YELLOW}{text}{Colors.RESET}"

def dim(text: str) -> str:
    return f"{Colors.DIM}{text}{Colors.RESET}"

def bold(text: str) -> str:
    return f"{Colors.BOLD}{text}{Colors.RESET}"


def status_dot(ok: bool = True) -> str:
    """Return a colored status dot."""
    if ok:
        return green(DOT)
    return red(DOT)


def success(message: str):
    """Print a success message."""
    print(f"  {green(CHECK)} {message}")


def error(message: str):
    """Print an error message."""
    print(f"  {red(CROSS)} {message}")


def warning(message: str):
    """Print a warning message."""
    print(f"  {yellow(WARN)} {message}")


def info(message: str):
    """Print an info message."""
    print(f"  {message}")


def mount_status(host: str, sandbox: str, ok: bool):
    """Print mount status line."""
    symbol = green(CHECK) if ok else red(CROSS)
    print(f"    {host} {dim(ARROW)} {sandbox} {symbol}")


def command_box(command: str):
    """Print command in a minimal box."""
    print(f"\n  {dim('┌ Command ─────────────────────────────────')}")
    print(f"  {dim('│')} {command}")
    print(f"  {dim('└──────────────────────────────────────────')}\n")


def risk_display(level: str, reason: str):
    """Display risk level with appropriate styling."""
    if level == "low":
        print(f"  Risk: {dim('low')} {dim('—')} {dim(reason)}")
    elif level == "medium":
        print(f"  {yellow(WARN)} Risk: {yellow('medium')} — {reason}")
    elif level == "high":
        print(f"  {red(WARN)} Risk: {red('high')} — {reason}")
    elif level == "blocked":
        print(f"  {red(CROSS)} {red('BLOCKED')} — {reason}")


class Spinner:
    """Animated spinner for thinking/loading states."""

    def __init__(self, message: str = "Thinking"):
        self.message = message
        self.running = False
        self.thread = None
        self.frame = 0

    def _animate(self):
        while self.running:
            frame = SPINNER_FRAMES[self.frame % len(SPINNER_FRAMES)]
            sys.stdout.write(f"\r  {orange(frame)} {self.message}...")
            sys.stdout.flush()
            self.frame += 1
            time.sleep(0.1)
        # Clear the line
        sys.stdout.write("\r" + " " * 40 + "\r")
        sys.stdout.flush()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._animate)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()


def print_banner(version: str = "0.1.0"):
    """Print the hermit banner."""
    print(f"""
       __
      (  )_
     (_____)_
    (________)
    //( 00 )\\\\

  {bold('hermit')} {dim(f'v{version}')}
""")


def print_status(sandboxed: bool):
    """Print status dots."""
    if sandboxed:
        print(f"  {green(DOT)} Sandbox active")
    else:
        print(f"  {yellow(DOT)} Sandbox {yellow('disabled')}")
    print(f"  {green(DOT)} OpenAI")
    print()

def print_tree(base_path: str, max_depth: int = 2, max_items: int = 8):
    """Print a tree view of the workspace."""
    import os
    from pathlib import Path

    def count_items(path):
        """Count files and folders in a directory."""
        try:
            items = list(Path(path).iterdir())
            files = sum(1 for i in items if i.is_file())
            dirs = sum(1 for i in items if i.is_dir())
            return files, dirs
        except PermissionError:
            return 0, 0

    def walk_tree(path, prefix="", depth=0):
        """Recursively print tree structure."""
        if depth > max_depth:
            return

        try:
            items = sorted(Path(path).iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            print(f"{prefix}{dim('(permission denied)')}")
            return

        # Separate dirs and files
        dirs = [i for i in items if i.is_dir()]
        files = [i for i in items if i.is_file()]

        # Show directories first
        for i, item in enumerate(dirs[:max_items]):
            is_last = (i == len(dirs) - 1) and len(files) == 0
            connector = "└── " if is_last else "├── "
            child_prefix = "    " if is_last else "│   "

            file_count, dir_count = count_items(item)
            info_parts = []
            if file_count:
                info_parts.append(f"{file_count} files")
            if dir_count:
                info_parts.append(f"{dir_count} folders")
            info = dim(f" ({', '.join(info_parts)})") if info_parts else ""

            print(f"  {prefix}{dim(connector)}{bold(item.name)}/{info}")

            if depth < max_depth:
                walk_tree(item, prefix + child_prefix, depth + 1)

        if len(dirs) > max_items:
            print(f"  {prefix}{dim('└── ')}...{dim(f' +{len(dirs) - max_items} more folders')}")

        # Show files (summarized at depth > 0)
        if files and depth == 0:
            for i, item in enumerate(files[:max_items]):
                is_last = i == len(files[:max_items]) - 1 and len(dirs) <= max_items
                connector = "└── " if is_last else "├── "
                print(f"  {prefix}{dim(connector)}{item.name}")
            if len(files) > max_items:
                print(f"  {prefix}{dim('└── ')}...{dim(f' +{len(files) - max_items} more files')}")
        elif files and depth > 0:
            if len(files) <= 3:
                names = ", ".join(f.name for f in files)
            else:
                names = ", ".join(f.name for f in files[:2]) + f", +{len(files) - 2} more"
            print(f"  {prefix}{dim('└── ')}{dim(names)}")

    print()
    print(f"  {bold('/workspace')}")

    if not os.path.exists(base_path):
        print(f"  {dim('(not mounted)')}")
        return

    walk_tree(base_path, "", 0)
    print()


def separator():
    """Print a separator line."""
    print(dim("─" * 44))


def prompt() -> str:
    """Get input with styled prompt."""
    try:
        return input(f"\n{orange('hermit')}{PROMPT} ")
    except EOFError:
        return "exit"
