import json
import os
from datetime import datetime
from pathlib import Path

AUDIT_LOG = Path.home() / ".hermit" / "audit.log"

def init_audit():
    """Create audit directory if needed."""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)

def log_event(event_type: str, data: dict):
    """Log an event to the audit file."""
    init_audit()
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        **data
    }
    
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

def log_command(user_input: str, generated_command: str):
    """Log when a command is generated."""
    log_event("command_generated", {
        "user_input": user_input,
        "command": generated_command
    })

def log_policy_check(command: str, allowed: bool, risk: str, reason: str):
    """Log policy engine decision."""
    log_event("policy_check", {
        "command": command,
        "allowed": allowed,
        "risk": risk,
        "reason": reason
    })

def log_execution(command: str, output: str, sandboxed: bool):
    """Log command execution."""
    log_event("execution", {
        "command": command,
        "output": output[:500],  # Truncate long output
        "sandboxed": sandboxed
    })

def log_blocked(command: str, reason: str):
    """Log blocked command."""
    log_event("blocked", {
        "command": command,
        "reason": reason
    })

def show_recent(n: int = 10):
    """Show recent audit entries."""
    if not AUDIT_LOG.exists():
        print("No audit log yet.")
        return
    
    with open(AUDIT_LOG) as f:
        lines = f.readlines()
    
    for line in lines[-n:]:
        entry = json.loads(line)
        ts = entry["timestamp"][:19]
        event = entry["type"]
        
        if event == "command_generated":
            print(f"[{ts}] 📝 \"{entry['user_input']}\" → {entry['command']}")
        elif event == "policy_check":
            status = "✓" if entry["allowed"] else "✗"
            print(f"[{ts}] {status} Policy: {entry['risk']} - {entry['reason']}")
        elif event == "execution":
            mode = "🔒" if entry["sandboxed"] else "🔓"
            print(f"[{ts}] {mode} Executed: {entry['command']}")
        elif event == "blocked":
            print(f"[{ts}] Blocked: {entry['command']} ({entry['reason']})")


if __name__ == "__main__":
    print(f"Audit log location: {AUDIT_LOG}\n")
    show_recent(20)