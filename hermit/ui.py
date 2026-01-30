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


def print_status(sandboxed: bool, backend: str):
    """Print status dots."""
    if sandboxed:
        print(f"  {green(DOT)} Sandbox active")
    else:
        print(f"  {yellow(DOT)} Sandbox {yellow('disabled')}")
    print(f"  {green(DOT)} Backend: {backend}")
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
