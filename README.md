# Hermit

Want to organize files, search code, or manage your system? 

Describe what you want in natural language, and Hermit translates it to safe, structured actions running in an isolated environment.

```
$ sudo hermit

       __
      (  )_
     (_____)_
    (________)
    //( 00 )\\

  hermit v0.1.0

  ⚠ Sandbox not initialized

  Run setup now? (y/n) y

  [1/7] Creating directory structure...
  [2/7] Copying binaries and dependencies...
  ✓ /bin/sh
  ✓ /usr/bin/touch
  ...

  ✓ Sandbox setup complete!

  ● Sandbox active
  ● OpenAI

  Mounting folders...
    ~/Downloads → /workspace/downloads ✓
    ~/projects → /workspace/projects ✓

  Ready. Type help for commands.

hermit> organize my downloads by file type

  ┌ Command ─────────────────────────────────
  │ organize_by_type /workspace/downloads
  └──────────────────────────────────────────

  Risk: medium — Moving files

  Run? (y/n) y

  ✓ Done
```

## Features

- **Natural language** → Describe tasks, Hermit figures out the commands
- **Structured actions** → LLM outputs JSON, not raw shell code
- **Sandboxed execution** → chroot + namespaces + seccomp filtering
- **Policy engine** → Risk-based approval with audit logging
- **Configurable** → Add folders, tweak safety settings via `config`

## Installation

```bash
# Clone and install
git clone https://github.com/beepboopdylan/hermit.git
cd hermit
pip install -e .

# Run (first run will set up sandbox automatically)
sudo hermit
```

Or install from GitHub directly:

```bash
pip install git+https://github.com/beepboopdylan/hermit.git
sudo hermit
```

## Usage

```bash
# Sandboxed mode (default, recommended)
sudo hermit

# Without sandbox (for development)
hermit --unsafe

# Show help
hermit --help
```

### Inside Hermit

```
hermit❯ help

  Commands:
    help                     Show this help
    config show              Show configuration
    config set <key> <val>   Set a preference
    config add-directory     Add a folder to sandbox
    audit                    Show command history
    exit                     Quit hermit

  Or just ask me to do something:
    "show my downloads"
    "organize files by type"
    "find all .py files"
```

## Configuration

Hermit stores config in `~/.hermit/config.json`:

```bash
# Add a folder to the sandbox
hermit❯ config add-directory ~/Music

# Change a setting
hermit❯ config set confirm_before_execute false

# View all settings
hermit❯ config show
```

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `confirm_before_execute` | `true` | Ask before running low-risk commands |
| `dry_run_by_default` | `false` | Show commands without executing |
| `block_rm_rf` | `true` | Block recursive force delete |
| `require_confirmation_for_delete` | `true` | Elevate delete ops to high risk |
| `max_files_per_operation` | `100` | Limit bulk operations |

## Security Layers

| Layer | Protection |
|-------|------------|
| **Structured actions** | LLM picks from a fixed menu; you build the commands |
| **chroot** | Filesystem restricted to `~/sandbox-root` |
| **PID namespace** | Process isolation — can't see host processes |
| **seccomp** | Blocks dangerous syscalls (reboot, mount, ptrace) |
| **Policy engine** | Regex-based blocking + risk levels (low/medium/high/blocked) |
| **Audit log** | Every command logged to `~/.hermit/audit.log` |

## Structured Actions

The LLM can only request these predefined actions:

```json
{"action": "list_files", "path": ".", "all": true, "long": true}
{"action": "read_file", "path": "filename"}
{"action": "create_file", "path": "filename", "content": "text"}
{"action": "delete_files", "path": ".", "pattern": "*.log"}
{"action": "move_file", "source": "old", "destination": "new"}
{"action": "create_directory", "path": "dirname"}
{"action": "find_files", "path": ".", "pattern": "*.py"}
{"action": "organize_by_type", "path": "/workspace/downloads"}
{"action": "run_command", "command": "..."}  // fallback only
```

Your code renders these to shell commands with proper escaping — the LLM never writes raw shell.

## Project Structure

```
hermit/
├── __init__.py
├── __main__.py        # python -m hermit
├── agent.py           # Main REPL
├── actions.py         # Structured action definitions
├── config.py          # Configuration management
├── policy.py          # Command risk assessment
├── mounts.py          # Sandbox mount handling
├── ui.py              # Terminal UI helpers
├── llm.py             # OpenAI integration
├── audit.py           # Command logging
├── sandbox_wrapper.py # Runs inside chroot
└── seccomp_filter.py  # Syscall filtering
```

## Requirements

- Linux (namespaces/seccomp are Linux-only)
- Python 3.10+
- OpenAI API key
- Root access (for sandbox mounts)

## License

MIT
