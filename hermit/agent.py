from dotenv import load_dotenv
load_dotenv()

import os
import subprocess
import sys
import signal
from hermit.policy import check_command, RiskLevel
from hermit.actions import parse_action
from hermit.mounts import setup_mounts, cleanup_mounts
from hermit.llm_backend import create_backend, LLMBackend
from hermit.config import load_config, get_preference, get_cgroup_config, set_active_backend
from hermit.config import ensure_setup, config_cli, get_preference, get_cgroup_config
from hermit.cgroups import setup_cgroup, cleanup_cgroup
from hermit import audit
from hermit import ui

SANDBOX_ROOT = "/home/ubuntu/sandbox-root"

def is_sandbox_ready() -> bool:
    """Check if sandbox environment is properly set up."""
    required = [
        f"{SANDBOX_ROOT}/bin/sh",
        f"{SANDBOX_ROOT}/usr/bin/touch",
        f"{SANDBOX_ROOT}/usr/bin/python3",
        f"{SANDBOX_ROOT}/sandbox/sandbox_wrapper.py",
    ]
    return all(os.path.exists(p) for p in required)


def ensure_sandbox():
    """Check sandbox and offer to set it up if needed."""
    if is_sandbox_ready():
        return True

    ui.print_banner()
    print(f"  {ui.yellow(ui.WARN)} Sandbox not initialized\n")

    confirm = input(f"  Run setup now? ({ui.green('y')}/{ui.dim('n')}) ")
    if confirm.lower() != 'y':
        print(f"\n  Run {ui.dim('sudo hermit-setup')} to initialize.\n")
        sys.exit(1)

    print()
    from hermit.setup_sandbox import main as run_setup
    run_setup()
    return True

SYSTEM_PROMPT = """You are Hermit, a secure shell assistant. Convert user requests to structured actions.

IMPORTANT: Return exactly ONE JSON object per response. No explanation, no markdown.

The user's files are mounted at:
- /workspace/downloads (their Downloads folder)
- /workspace/projects (their projects folder)

Available actions:

{"action": "list_files", "path": "/workspace/downloads", "all": false, "long": false}
{"action": "read_file", "path": "filename"}
{"action": "create_file", "path": "filename", "content": "text"}
{"action": "delete_files", "path": ".", "pattern": "*.log", "recursive": false}
{"action": "move_file", "source": "old", "destination": "new"}
{"action": "create_directory", "path": "dirname"}
{"action": "find_files", "path": ".", "pattern": "*.py", "file_type": "file"}
{"action": "organize_by_type", "path": "/workspace/downloads"}
{"action": "run_command", "command": "echo hello"}

For BATCH operations (creating/deleting multiple files), use run_command with brace expansion:
- Create 10 files: {"action": "run_command", "command": "touch /workspace/projects/file{1..10}.py"}
- Delete all .tmp: {"action": "delete_files", "path": "/workspace/downloads", "pattern": "*.tmp"}

Examples:
User: "show my downloads" → {"action": "list_files", "path": "/workspace/downloads", "all": true, "long": true}
User: "create 5 test files" → {"action": "run_command", "command": "touch /workspace/projects/test{1..5}.txt"}
User: "organize downloads by type" → {"action": "organize_by_type", "path": "/workspace/downloads"}
"""

# Global for cleanup on exit
mounted_paths = []
cleanup_done = False
llm_backend: LLMBackend = None

def init_llm_backend():
    """Initialize LLM backend from config."""
    global llm_backend
    from hermit import ui
    config = load_config()
    llm_backend = create_backend(config)
    
    if not llm_backend.is_available():
        ui.error(f"Backend not configured properly")
        sys.exit(1)

    if config.get("llm_backend") == "llamacpp":
        ui.info("Loading model...")
        try:
            # This triggers the lazy load
            llm_backend._get_llm()
        except Exception as e:
            ui.error(f"Failed to load model: {e}")
            sys.exit(1)
    
    return llm_backend


def get_action(user_input: str) -> str:
    """Ask LLM to return a structured JSON action."""
    global llm_backend
    return llm_backend.get_completion(SYSTEM_PROMPT, user_input)


def execute_unsafe(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def execute_sandboxed(command: str) -> str:
    # Get timeout from config
    cgroup_cfg = get_cgroup_config()
    timeout = cgroup_cfg.get('timeout_seconds', 30)

    # Use bash wrapper to add process to cgroup BEFORE running unshare
    # This ensures the unshare process and all children are in the cgroup
    cgroup_path = "/sys/fs/cgroup/hermit-sandbox"
    wrapper_command = f'''
        echo $$ > {cgroup_path}/cgroup.procs
        exec unshare --mount --pid --fork --mount-proc \
            chroot {SANDBOX_ROOT} \
            /usr/bin/python3 /sandbox/sandbox_wrapper.py '{command.replace("'", "'\"'\"'")}'
    '''

    process = subprocess.Popen(
        ["bash", "-c", wrapper_command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait for completion with timeout
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return stdout + stderr
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()  # Clean up
        return f"Command timed out after {timeout} seconds"


def cleanup_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global cleanup_done
    if not cleanup_done:
        print("\n")
        ui.info("Cleaning up...")
        cleanup_mounts(mounted_paths)
        cleanup_cgroup()
        cleanup_done = True
    print("  Goodbye!")
    sys.exit(0)


def show_help():
    """Show help with styled output."""
    ui.print_banner()
    print(f"  {ui.bold('Sandboxed AI Shell Assistant')}")
    print()
    print(f"  {ui.dim('Usage:')} sudo hermit [OPTIONS]")
    print()
    print(f"  {ui.dim('Options:')}")
    print(f"    --unsafe     Disable sandbox (not recommended)")
    print(f"    --help       Show this help message")
    print()
    print(f"  {ui.dim('Commands (inside hermit):')}")
    print(f"    help                        Show commands")
    print(f"    tree                        Show workspace structure")
    print(f"    config show                 Show configuration")
    print(f"    config backend <name>       Switch LLM backend")
    print(f"    config set <key> <val>      Set a preference")
    print(f"    config add-directory <path> Add folder to sandbox")
    print(f"    config remove-directory     Remove folder")
    print(f"    audit                       Show command history")
    print(f"    clear                       Clear conversation")
    print(f"    exit                        Quit hermit")
    print()
    
def show_inline_help():
    """Show help when inside the REPL."""
    print()
    print(f"  {ui.bold('Commands:')}")
    print(f"    {ui.dim('help')}                     Show this help")
    print(f"    {ui.dim('tree')}                     Show workspace structure")
    print(f"    {ui.dim('config show')}              Show configuration")
    print(f"    {ui.dim('config set <key> <val>')}   Set a preference")
    print(f"    {ui.dim('config add-directory')}     Add a folder to sandbox")
    print(f"    {ui.dim('audit')}                    Show command history")
    print(f"    {ui.dim('clear')}                    Clear conversation history")
    print(f"    {ui.dim('exit')}                     Quit hermit")
    print()
    print(f"  {ui.bold('Or just ask me to do something:')}")
    print(f"    {ui.dim('\"show my downloads\"')}")
    print(f"    {ui.dim('\"organize files by type\"')}")
    print(f"    {ui.dim('\"find all .py files\"')}")
    print()


def main():
    global mounted_paths, cleanup_done

    # Handle --help before setup
    if "--help" in sys.argv or "-h" in sys.argv:
        show_help()
        return

    sandboxed = "--unsafe" not in sys.argv

    # Check sandbox is ready (only in sandboxed mode)
    if sandboxed:
        ensure_sandbox()

    # Check API key is configured
    ensure_setup()

    init_llm_backend()
    
    ui.print_banner()
    ui.print_status(sandboxed)

    print(f"  {ui.green(ui.DOT)} LLM: {llm_backend.get_name()}")

    if sandboxed:
        print(f"  {ui.dim('Mounting folders...')}")
        mounted_paths = setup_mounts()
        print(f"  {ui.dim('Setting up cgroups...')}")
        cgroup_cfg = get_cgroup_config()
        setup_cgroup(
            memory_max_mb=cgroup_cfg.get('memory_max_mb', 512),
            cpu_quota_percent=cgroup_cfg.get('cpu_quota_percent', 50),
            pids_max=cgroup_cfg.get('pids_max', 100)
        )
        print()
        signal.signal(signal.SIGINT, cleanup_handler)
    else:
        ui.warning("Sandbox disabled - commands run directly on your system")
        print()

    print(f"  Ready. Type {ui.dim('help')} for commands.")
    ui.separator()

    try:
        while True:
            user_input = ui.prompt()

            if user_input.lower() in ['exit', 'quit']:
                break

            if not user_input:
                continue

            if user_input.lower() in ['help', '?']:
                show_inline_help()
                continue

            if user_input.lower() == 'audit':
                audit.show_recent(10)
                continue
            
            if user_input.lower() == 'clear':
                llm_backend.clear_history()
                print("Conversation history cleared.")
                continue

            if user_input.lower() == 'tree':
                ui.print_tree(f"{SANDBOX_ROOT}/workspace")
                continue

            if user_input.lower().startswith('config'):
                args = user_input.split()[1:] if len(user_input.split()) > 1 else []

                if len(args) >= 2 and args[0] == "backend":
                    if set_active_backend(args[1]):
                        init_llm_backend()
                        print(f"  ✓ Switched to {llm_backend.get_name()}")
                    else:
                        print(f"  ✗ Backend '{args[1]}' not configured")
                    continue
                
                config_cli(args)
                continue

            # Get action from LLM with spinner
            spinner = ui.Spinner("Thinking")
            spinner.start()
            try:
                action = parse_action(get_action(user_input))
            finally:
                spinner.stop()

            command = action.render()

            # Show what we're doing
            ui.info(action.describe())
            ui.command_box(command)

            audit.log_command(user_input, command)

            policy = check_command(command)
            audit.log_policy_check(command, policy.allowed, policy.risk.value, policy.reason)

            # Handle policy result
            if not policy.allowed:
                ui.risk_display("blocked", policy.reason)
                audit.log_blocked(command, policy.reason)
                continue

            ui.risk_display(policy.risk.value, policy.reason)

            if policy.risk == RiskLevel.HIGH:
                confirm = input(f"\n  Type '{ui.orange('yes')}' to confirm: ")
                if confirm.lower() != 'yes':
                    ui.info("Cancelled.")
                    continue
            elif policy.risk == RiskLevel.MEDIUM:
                confirm = input(f"  Run? ({ui.green('y')}/{ui.dim('n')}) ")
                if confirm.lower() != 'y':
                    ui.info("Cancelled.")
                    continue
            else:
                if get_preference("confirm_before_execute"):
                    confirm = input(f"  Run? ({ui.green('y')}/{ui.dim('n')}) ")
                    if confirm.lower() != 'y':
                        ui.info("Cancelled.")
                        continue

            # Execute
            if sandboxed:
                output = execute_sandboxed(command)
            else:
                output = execute_unsafe(command)

            ui.success("Done")

            if output and output.strip():
                print()
                print(ui.dim("  " + output.replace("\n", "\n  ")))

    finally:
        if sandboxed and mounted_paths and not cleanup_done:
            print()
            ui.info("Cleaning up...")
            cleanup_mounts(mounted_paths)
            cleanup_cgroup()
            cleanup_done = True


if __name__ == "__main__":
    main()
