from dotenv import load_dotenv
load_dotenv()

import subprocess
from openai import OpenAI
from policy import check_command, RiskLevel
import audit

client = OpenAI()
MODEL = "gpt-4o-mini"

SANDBOX_ROOT = "/home/ubuntu/sandbox-root"

def get_command(user_input: str) -> str:
    """

    Asking OpenAI to generate a shell command

    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role":"system",
            "content":"You're a Linux shell expert. Convert user requests into shell commands. Reply with ONLY the command, no explanation, no markdown, no code blocks."
        }, {
            "role":"user",
            "content":user_input
        }],
        max_tokens=256
    )
    return response.choices[0].message.content.strip()

def execute_unsafe(command: str) -> str:
    """Execute command and return output."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True
    )
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

def main():
    import sys
    sandboxed = "--sandbox" in sys.argv

    if sandboxed:
        print(f"🔒 Sandboxed Agent (using {MODEL})")
        print(f"   Filesystem restricted to: {SANDBOX_ROOT}")
        print("   PID namespace isolation: active")
    else:
        print(f"🔓 Unsafe Agent (using {MODEL})")
        print("   No sandbox yet - be careful!")
    print("   Type 'exit' to quit\n")

    while True:
        user_input = input("> ")

        if user_input.lower() in ['exit', 'quit']:
            break
        if not user_input:
            continue
        
        if user_input.lower() == 'audit':
            audit.show_recent(10)
            continue
        
        command = get_command(user_input)
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

if __name__ == "__main__":
    main()