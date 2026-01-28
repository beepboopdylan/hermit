# Hermit

A sandboxed AI shell agent. Describe what you want in natural language, and Hermit translates it to shell commands and runs them in an isolated environment.

## Features

- **Natural language to shell** - Powered by OpenAI
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

# Run hermit
hermit "find all python files"
```

## Usage

### One-shot CLI (hermit)
```bash
hermit "show disk usage"
hermit "find files larger than 10MB"
hermit "count lines in all .py files"
```

### Interactive mode (agent.py)
```bash
sudo venv/bin/python src/agent.py --sandbox
> list all files
> show system info
> audit        # view command history
> exit
```

## Security Layers

| Layer | Protection |
|-------|------------|
| **chroot** | Filesystem restricted to `~/sandbox-root` |
| **PID namespace** | Process isolation - can't see host processes |
| **seccomp** | Blocks: reboot, mount, ptrace, kernel modules |
| **Network** | Socket syscalls return EPERM |
| **Policy** | Regex-based command blocking + risk levels |

## Project Structure

```
sandboxed-agent/
├── hermit              # CLI wrapper (requires sudo)
├── src/
│   ├── hermit.py       # One-shot CLI
│   ├── agent.py        # Interactive REPL with policy engine
│   ├── sandbox_wrapper.py  # Runs inside chroot, applies seccomp
│   ├── policy.py       # Command risk assessment
│   └── audit.py        # Logging
└── ~/sandbox-root/     # Chroot jail with minimal binaries
```

## Requirements

- Linux (namespaces/seccomp are Linux-only)
- Python 3.10+
- OpenAI API key
- Root access (for unshare/chroot)