# Hermit

A sandboxed AI shell agent. Describe what you want in natural language, and Hermit translates it to structured actions and runs them in an isolated environment.

## Features

- **Structured actions** - LLM returns JSON, not raw shell (v2)
- **Filesystem isolation** - Commands run in a chroot jail (`~/sandbox-root`)
- **Process isolation** - PID namespace via `unshare`
- **Syscall filtering** - seccomp blocks dangerous operations (reboot, mount, ptrace, network)
- **Policy engine** - Risk-based command approval with audit logging

## Quick Start

```bash
# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install openai python-dotenv

# Set up your API key
echo "OPENAI_API_KEY=sk-..." > .env

# Run (requires sudo for namespaces)
sudo venv/bin/python src/agent.py --sandbox
```

## Usage

```bash
sudo venv/bin/python src/agent.py --sandbox

🔒 Hermit (sandboxed mode)
   Security: namespaces + chroot + seccomp + policy engine
   Output: structured actions
   Type 'exit' to quit, 'audit' for history

🦀 > show all files
Action: List files in .
Command: ls -al
Execute? [y/N] y
```

## v1 vs v2

| | v1 (raw shell) | v2 (structured actions) |
|--|----------------|------------------------|
| LLM output | `ls -la; rm -rf /` | `{"action": "list_files", "path": "."}` |
| Command built by | LLM | Your code |
| Injection risk | High | Low (params escaped) |
| Tag | `v1.0.0` | Current |

## Structured Actions

LLM can only use these predefined actions:

```json
{"action": "list_files", "path": ".", "all": true, "long": true}
{"action": "read_file", "path": "filename"}
{"action": "create_file", "path": "filename", "content": "text"}
{"action": "delete_files", "path": ".", "pattern": "*.log", "recursive": false}
{"action": "move_file", "source": "old", "destination": "new"}
{"action": "create_directory", "path": "dirname"}
{"action": "find_files", "path": ".", "pattern": "*.py"}
{"action": "run_command", "command": "..."}  # fallback
```

Your code renders these to shell commands with proper escaping.

## Security Layers

| Layer | Protection |
|-------|------------|
| **Structured actions** | LLM picks from fixed menu, you build commands |
| **chroot** | Filesystem restricted to `~/sandbox-root` |
| **PID namespace** | Process isolation - can't see host processes |
| **seccomp** | Blocks: reboot, mount, ptrace, kernel modules |
| **Network** | Socket syscalls return EPERM |
| **Policy** | Regex-based command blocking + risk levels |

## Project Structure

```
sandboxed-agent/
├── src/
│   ├── agent.py           # Main REPL
│   ├── actions.py         # Structured action definitions
│   ├── sandbox_wrapper.py # Runs inside chroot, applies seccomp
│   ├── policy.py          # Command risk assessment
│   └── audit.py           # Logging
└── ~/sandbox-root/        # Chroot jail with minimal binaries
```

## Requirements

- Linux (namespaces/seccomp are Linux-only)
- Python 3.10+
- OpenAI API key
- Root access (for unshare/chroot)
