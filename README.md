# Sandboxed AI Shell Agent

An AI-powered shell assistant that executes commands in a secure Linux sandbox using namespaces and seccomp.

## Features
- Natural language → shell commands (via OpenAI)
- PID namespace isolation
- (More coming: mount namespace, seccomp, policy engine)

## Usage
```bash
# Unsafe mode
python3 src/agent.py

# Sandboxed mode (requires root)
sudo python3 src/agent.py --sandbox
```

## Requirements
- Linux (namespaces are Linux-only)
- Python 3.10+
- OpenAI API key
