from dotenv import load_dotenv
load_dotenv()

import os
import subprocess
import sys
import signal
import json
from pathlib import Path
from hermit.policy import check_command, RiskLevel
from hermit.actions import parse_action
from hermit.mounts import setup_mounts, cleanup_mounts, mount_dr, unmount_dr, list_mounts
from hermit.llm_backend import create_backend, LLMBackend
from hermit.config import load_config, save_config, get_preference, get_cgroup_config, set_active_backend
from hermit.config import ensure_setup, config_cli, get_preference, get_cgroup_config
from hermit.cgroups import setup_cgroup, cleanup_cgroup
from hermit.planner import system_prompt, parse_plan
from hermit.executor import execute_plan
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
    return llm_backend.get_completion(system_prompt(), user_input)


def execute_unsafe(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def execute_sandboxed(command: str) -> str:
    # Get timeout from config
    cgroup_cfg = get_cgroup_config()
    timeout = cgroup_cfg.get('timeout_seconds', 30)

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

def show_plan_preview(plan):
    """Display a multi-step plan for user review."""
    print()
    ui.info(f"Plan: {plan.description}")
    print(f"  {ui.dim(f'{len(plan)} steps:')}")
    print()
    for i, step in enumerate(plan.steps):
        deps = ""
        if step.depends_on:
            deps = ui.dim(f" (after step {', '.join(str(d) for d in step.depends_on)})")
        print(f"    {i + 1}. {step.description}{deps}")
    print()

def get_user_approval(risk_level: str) -> bool:
    """Approval callback for the executor."""
    if risk_level == "high":
        confirm = input(f"\n  Type '{ui.orange('yes')}' to confirm: ")
        return confirm.lower() == "yes"
    confirm = input(f"  Run? ({ui.green('y')}/{ui.dim('n')}) ")
    return confirm.lower() == 'y'


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
    print(f"    mounts                      Show mounted folders")
    print(f"    mount <path>                Add and mount a folder")
    print(f"    unmount <path>              Unmount (this session)")
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
    print(f"    {ui.dim('mounts')}                   Show mounted folders")
    print(f"    {ui.dim('mount <path>')}             Add and mount a folder")
    print(f"    {ui.dim('unmount <path>')}           Unmount a folder (this session)")
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

    exec_fn = execute_sandboxed if sandboxed else execute_unsafe

    try:
        while True:
            user_input = ui.prompt()
            input = user_input.lower()

            if not input:
                continue
            
            if input in ['exit', 'quit']:
                break

            if input in ['help', '?']:
                show_inline_help()
                continue

            if input == 'audit':
                audit.show_recent(10)
                continue
            
            if input == 'clear':
                llm_backend.clear_history()
                print("Conversation history cleared.")
                continue

            if input == 'tree':
                ui.print_tree(f"{SANDBOX_ROOT}/workspace")
                continue

            if input == "mounts":
                list_mounts(mounted_paths)
                continue

            if input.startswith("mount "):
                path = user_input.split(None, 1)[1].strip()
                from hermit.config import add_directory, get_allowed_directories

                if not os.path.exists(os.path.expanduser(path)):
                    ui.error(f"Path does not exist: {path}")
                    continue

                if add_directory(path):
                    ui.info(f"Added {path} to config")
                
                for d in get_allowed_directories():
                    if d["host"] == path or d["host"] == path.replace(str(Path.home()), "~"):
                        res = mount_dr(d["host"], d["sandbox"])
                        if res:
                            mounted_paths.append(res)
                        break
                else:
                    ui.error(f"Could not find {path} in config")
                continue
            if input.startswith("unmount "):
                path = user_input.split(None, 1)[1].strip()
                from hermit.config import get_allowed_directories

                for d in get_allowed_directories():
                    if d["host"] == path or d["host"] == path.replace(str(Path.home()), "~"):
                        sandbox_full = f"{SANDBOX_ROOT}{d['sandbox']}"
                        if sandbox_full in mounted_paths:
                            if unmount_dr(d["sandbox"]):
                                mounted_paths.remove(sandbox_full)
                                ui.success(f"Unmounted {path} (still in config for next session)")
                            else:
                                ui.error(f"Failed to unmount {path}")
                        else:
                            ui.info(f"{path} is not currently mounted")
                        break
                else:
                    ui.error(f"{path} not found in config")
                continue

            if input.startswith('config'):
                args = user_input.split()[1:] if len(user_input.split()) > 1 else []

                if len(args) >= 2 and args[0] == "backend":
                    backend_name = args[1]
                    if set_active_backend(backend_name):
                        init_llm_backend()
                        print(f"  {ui.green(ui.CHECK)} Switched to {llm_backend.get_name()}")
                    else:
                        # Actually help the user instead of dead-ending
                        config = load_config()
                        if backend_name == "openai" and not config.get("openai_configured"):
                            print(f"  {ui.yellow(ui.WARN)} OpenAI not configured yet.\n")
                            key = input(f"  Enter API key (from {ui.dim('platform.openai.com/api-keys')}): ").strip()
                            if key.startswith("sk-") and len(key) > 20:
                                config["openai_key"] = key
                                config["openai_configured"] = True
                                config["llm_backend"] = "openai"
                                save_config(config)
                                init_llm_backend()
                                print(f"  {ui.green(ui.CHECK)} Switched to {llm_backend.get_name()}")
                            elif key:
                                ui.error("Invalid key format. Should start with 'sk-'")
                            else:
                                ui.info("Cancelled.")
                        elif backend_name == "llamacpp" and not config.get("llamacpp_configured"):
                            print(f"  {ui.yellow(ui.WARN)} llama.cpp not configured yet.")
                            print(f"  Run {ui.dim('hermit')} without sudo to re-run setup.")
                        else:
                            ui.error(f"Unknown backend '{backend_name}'. Options: openai, llamacpp")
                    continue                
                config_cli(args)
                continue

            # Get action from LLM with spinner
            spinner = ui.Spinner()
            spinner.start()
            try:
                raw_plan = llm_backend.get_completion(system_prompt(), user_input)
                plan = parse_plan(raw_plan)
            except Exception as e:
                spinner.stop()
                ui.error(f"Failed to parse plan: {e}")
                print(f"  {ui.dim('Raw:')} {raw_plan}")
                continue
            finally:
                spinner.stop()

            audit.log_command(user_input, f"plan:{len(plan)} steps")

            if len(plan) == 1:
                # simple
                step = plan.steps[0]
                action = parse_action(json.dumps(step.action_json))

                command = action.render()

                ui.info(action.describe())
                ui.command_box(command)

                policy = check_command(command)
                audit.log_policy_check(command, policy.allowed, policy.risk.value, policy.reason)

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

                output = exec_fn(command)
                audit.log_execution(command, output, sandboxed)
                ui.success("Done")

                if output and output.strip():
                    print()
                    print(ui.dim("  " + output.replace("\n", "\n  ")))

            else:
                show_plan_preview(plan)

                print(f"    1. Step by step  2. Run all")
                
                choice = input(f"  Select (1/2/n): ")

                if choice == "1":
                    step_by_step = True
                elif choice == "2":
                    step_by_step = False
                else:
                    ui.info("Cancelled.")
                    continue

                print()
                execute_plan(plan, exec_fn, get_user_approval, step_by_step)

    finally:
        if sandboxed and mounted_paths and not cleanup_done:
            print()
            ui.info("Cleaning up...")
            cleanup_mounts(mounted_paths)
            cleanup_cgroup()
            cleanup_done = True


if __name__ == "__main__":
    main()
