from dotenv import load_dotenv
load_dotenv()

import subprocess
import sys
import json
import signal
from openai import OpenAI
from policy import check_command, RiskLevel
from actions import parse_action, RunCommand
from mounts import setup_mounts, cleanup_mounts, list_mounts
import audit

client = OpenAI()
MODEL = "gpt-4o-mini"

SANDBOX_ROOT = "/home/ubuntu/sandbox-root"

SYSTEM_ROOT = """You are Hermit, a secure shell assistant. Convert user requests to structured actions.

Respond with ONLY valid JSON. No explanation, no markdown.

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

Use run_command only if no other action fits.

Examples:
User: "show my downloads" → {"action": "list_files", "path": "/workspace/downloads", "all": true, "long": true}
User: "organize downloads by type" → {"action": "organize_by_type", "path": "/workspace/downloads"}
User: "what projects do I have" → {"action": "list_files", "path": "/workspace/projects", "long": true}
"""

# Global for cleanup on exit
mounted_paths = []

def get_action(user_input: str) -> str:
    """Ask LLM to return a structured JSON action."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "system",
            "content": SYSTEM_ROOT
        }, {
            "role": "user",
            "content": user_input
        }],
        max_tokens=256
    )
    return response.choices[0].message.content.strip()

def execute_unsafe(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr

def execute_sandboxed(command: str) -> str:
    full_command = [
        "unshare",
        "--mount",
        "--pid",
        "--fork",
        "--mount-proc",
        "chroot", SANDBOX_ROOT,
        "/usr/bin/python3", "/sandbox/sandbox_wrapper.py", command
    ]

    result = subprocess.run(
        full_command,
        capture_output=True,
        text=True
    )
    return result.stdout + result.stderr

def cleanup_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\nCleaning up...")
    cleanup_mounts(mounted_paths)
    print("Goodbye!")
    sys.exit(0)


def main():
    global mounted_paths
    sandboxed = "--sandbox" in sys.argv

    if sandboxed:
        print(f"🔒 Hermit (sandboxed mode)")
        print("   Security: namespaces + chroot + seccomp + policy engine\n")
        
        list_mounts()
        mounted_paths = setup_mounts()
        
        signal.signal(signal.SIGINT, cleanup_handler)
        
        print("\n   Type 'exit' to quit, 'audit' for history\n")
    else:
        print(f"🔓 Hermit (unsafe mode)")
        print("   No sandbox - be careful!")
        print("   Type 'exit' to quit, 'audit' for history\n")
    try:
        while True:
            user_input = input("🦀 > ")

            if user_input.lower() in ['exit', 'quit']:
                break
            if not user_input:
                continue
            
            if user_input.lower() == 'audit':
                audit.show_recent(10)
                continue

            action = parse_action(get_action(user_input))

            command = action.render()

            print(f"Action: {action.describe()}")
            print(f"Command: {command}")

            audit.log_command(user_input, command)

            policy = check_command(command)
            audit.log_policy_check(command, policy.allowed, policy.risk.value, policy.reason)

            if not policy.allowed:
                print(f"BLOCKED [{policy.risk.value}]: {policy.reason}")
                audit.log_blocked(command, policy.reason)
                continue
            if policy.risk == RiskLevel.HIGH:
                print(f"HIGH RISK: {policy.reason}")
                confirm = input("Type 'yes' to confirm: ")
                if confirm.lower() != 'yes':
                    print("Cancelled.")
                    continue
            elif policy.risk == RiskLevel.MEDIUM:
                print(f"⚡ {policy.reason}")
                confirm = input("Execute? [y/N] ")
                if confirm.lower() != 'y':
                    continue
            else:
                confirm = input("Execute? [y/N] ")
                if confirm.lower() != 'y':
                    print("Cancelled.")
                    continue

            if sandboxed:
                output = execute_sandboxed(command)
            else:
                output = execute_unsafe(command)
            print(output if output else "(no output)")
    finally:
        if sandboxed and mounted_paths:
            print("\n🦀 Cleaning up...")
            cleanup_mounts(mounted_paths)

if __name__ == "__main__":
    main()