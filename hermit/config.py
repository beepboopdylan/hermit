import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".hermit"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    # LLM settings
    "openai_key": None,
    "openai_model": "gpt-4o-mini",
    "setup_complete": False,

    # Directory mappings (host -> sandbox)
    "allowed_directories": [
        {"host": "~/Downloads", "sandbox": "/workspace/downloads"},
        {"host": "~/projects", "sandbox": "/workspace/projects"},
    ],

    # User preferences
    "preferences": {
        "confirm_before_execute": True,
        "dry_run_by_default": False,
        "auto_organize_extensions": {
            "images": ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"],
            "documents": ["pdf", "doc", "docx", "txt", "md", "rtf", "odt"],
            "audio": ["mp3", "wav", "flac", "aac", "ogg", "m4a"],
            "video": ["mp4", "mov", "avi", "mkv", "webm", "wmv"],
            "archives": ["zip", "tar", "gz", "rar", "7z"],
            "code": ["py", "js", "ts", "java", "c", "cpp", "go", "rs"],
        }
    },

    # Safety settings
    "safety": {
        "block_rm_rf": True,
        "require_confirmation_for_delete": True,
        "max_files_per_operation": 100,
    },

    # Cgroup resource limits
    "cgroups": {
        "enabled": True,
        "memory_max_mb": 512,
        "cpu_quota_percent": 50,
        "pids_max": 100,
        "timeout_seconds": 60,
    }
}

def load_config() -> dict:
    """Load config from disk, or return defaults."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            # Merge with defaults for any missing keys
            return {**DEFAULT_CONFIG, **config}
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    """Save config to disk"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

"""

Directory Management

"""

def get_allowed_directories() -> list:
    """Get list of allowed directory mappings."""
    config = load_config()
    return config.get("allowed_directories", DEFAULT_CONFIG["allowed_directories"])

def add_directory(host_path: str, sandbox_name: str = None) -> bool:
    """Add a new directory to allowed_directories.

    Args:
        host_path: Path on host (e.g., ~/Music)
        sandbox_name: Optional name in sandbox (defaults to folder name)

    Returns:
        True if added, False if already exists
    """
    config = load_config()

    # Normalize the path
    if host_path.startswith("~"):
        display_path = host_path
    else:
        display_path = str(Path(host_path).expanduser())
        if display_path.startswith(str(Path.home())):
            display_path = "~" + display_path[len(str(Path.home())):]

    # Generate sandbox path if not provided
    if sandbox_name is None:
        folder_name = Path(host_path).expanduser().name.lower()
        sandbox_name = folder_name

    sandbox_path = f"/workspace/{sandbox_name}"

    # Check if already exists
    for d in config.get("allowed_directories", []):
        if d["host"] == display_path or d["sandbox"] == sandbox_path:
            return False

    config.setdefault("allowed_directories", []).append({
        "host": display_path,
        "sandbox": sandbox_path
    })
    save_config(config)
    return True

def remove_directory(host_path: str) -> bool:
    """Remove a directory from allowed_directories."""
    config = load_config()
    dirs = config.get("allowed_directories", [])

    # Normalize for comparison
    if not host_path.startswith("~"):
        expanded = str(Path(host_path).expanduser())
        if expanded.startswith(str(Path.home())):
            host_path = "~" + expanded[len(str(Path.home())):]

    original_len = len(dirs)
    config["allowed_directories"] = [d for d in dirs if d["host"] != host_path]

    if len(config["allowed_directories"]) < original_len:
        save_config(config)
        return True
    return False

"""

Preferences Management

"""

def get_preference(key: str):
    """Get a preference value by key (supports dot notation)."""
    config = load_config()
    prefs = config.get("preferences", DEFAULT_CONFIG["preferences"])

    # Support dot notation: "auto_organize_extensions.images"
    keys = key.split(".")
    value = prefs
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return None
    return value

def set_preference(key: str, value) -> bool:
    """Set a preference value. Returns True on success."""
    config = load_config()
    config.setdefault("preferences", {})

    # Handle dot notation
    keys = key.split(".")
    target = config["preferences"]

    for k in keys[:-1]:
        target = target.setdefault(k, {})

    # Type conversion for common values
    if isinstance(value, str):
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        elif value.isdigit():
            value = int(value)

    target[keys[-1]] = value
    save_config(config)
    return True

"""

Safety Settings Management

"""

def get_safety_setting(key: str):
    """Get a safety setting value."""
    config = load_config()
    safety = config.get("safety", DEFAULT_CONFIG["safety"])
    return safety.get(key)

def set_safety_setting(key: str, value) -> bool:
    """Set a safety setting. Returns True on success."""
    config = load_config()
    config.setdefault("safety", {})

    # Type conversion
    if isinstance(value, str):
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        elif value.isdigit():
            value = int(value)

    config["safety"][key] = value
    save_config(config)
    return True

"""

Cgroup Settings Management

"""

def get_cgroup_config() -> dict:
    """Get cgroup configuration."""
    config = load_config()
    return config.get("cgroups", DEFAULT_CONFIG["cgroups"])

def is_cgroups_enabled() -> bool:
    """Check if cgroups are enabled in config."""
    cgroup_config = get_cgroup_config()
    return cgroup_config.get("enabled", True)

"""

Config Display

"""

def show_config():
    """Display current configuration in a readable format."""
    config = load_config()

    print("\n" + "=" * 50)
    print("  HERMIT CONFIGURATION")
    print("=" * 50)

    # LLM Settings
    print("\n[LLM Settings]")
    key = config.get('openai_key', '')
    masked = key[:7] + '...' + key[-4:] if key and len(key) > 15 else '(not set)'
    print(f"  OpenAI Key: {masked}")
    print(f"  Model: {config.get('openai_model', 'gpt-4o-mini')}")

    # Directories
    print("\n[Allowed Directories]")
    for d in config.get("allowed_directories", []):
        host = d["host"]
        sandbox = d["sandbox"]
        expanded = str(Path(host).expanduser())
        exists = "✓" if Path(expanded).exists() else "✗"
        print(f"  {exists} {host} → {sandbox}")

    # Preferences
    print("\n[Preferences]")
    prefs = config.get("preferences", {})
    print(f"  Confirm before execute: {prefs.get('confirm_before_execute', True)}")
    print(f"  Dry run by default: {prefs.get('dry_run_by_default', False)}")

    # Safety
    print("\n[Safety]")
    safety = config.get("safety", {})
    print(f"  Block rm -rf: {safety.get('block_rm_rf', True)}")
    print(f"  Confirm deletes: {safety.get('require_confirmation_for_delete', True)}")
    print(f"  Max files per op: {safety.get('max_files_per_operation', 100)}")

    # Cgroups
    print("\n[Resource Limits (cgroups)]")
    cgroups = config.get("cgroups", {})
    print(f"  Enabled: {cgroups.get('enabled', True)}")
    print(f"  Memory max: {cgroups.get('memory_max_mb', 512)} MB")
    print(f"  CPU quota: {cgroups.get('cpu_quota_percent', 50)}%")
    print(f"  Max PIDs: {cgroups.get('pids_max', 100)}")
    print(f"  Timeout: {cgroups.get('timeout_seconds', 30)}s")

    print("\n" + "=" * 50)
    print(f"  Config file: {CONFIG_FILE}")
    print("=" * 50 + "\n")

def first_run_setup() -> dict:
    """Interactive first-run setup. Returns config."""
    # Import here to avoid circular imports
    from hermit import ui

    ui.print_banner()
    print(f"  {ui.bold('First Time Setup')}")
    print()
    print(f"  Get your API key from: {ui.dim('https://platform.openai.com/api-keys')}")
    print()

    config = load_config()

    while True:
        key = input(f"  OpenAI API key: ").strip()
        if key.startswith("sk-") and len(key) > 20:
            break
        ui.error("Invalid key format. Should start with 'sk-'")

    config["openai_key"] = key
    config["setup_complete"] = True
    save_config(config)

    print()
    ui.success("OpenAI configured!")
    ui.info(f"Config saved to {ui.dim('~/.hermit/config.json')}")
    print()
    return config

def ensure_setup() -> dict:
    """Make sure setup is complete. Returns config."""
    config = load_config()

    if not config["setup_complete"]:
        return first_run_setup()

    return config

"""

CLI Interface

"""

def config_cli(args: list) -> bool:
    """Handle 'hermit config' subcommands.

    Usage:
        hermit config show                    - Show all configuration
        hermit config set <key> <value>       - Set a preference or safety setting
        hermit config add-directory <path>    - Add a directory to allowed list
        hermit config remove-directory <path> - Remove a directory
        hermit config reset                   - Reset to defaults

    Returns True if command was handled, False otherwise.
    """
    if not args:
        print("Usage: hermit config <command>")
        print("Commands: show, set, add-directory, remove-directory, reset")
        return True

    cmd = args[0].lower()

    if cmd == "show":
        show_config()
        return True

    elif cmd == "set" and len(args) >= 3:
        key = args[1]
        value = " ".join(args[2:])

        # Determine if it's a preference or safety setting
        safety_keys = ["block_rm_rf", "require_confirmation_for_delete", "max_files_per_operation"]

        if key in safety_keys:
            if set_safety_setting(key, value):
                print(f"✓ Set safety.{key} = {value}")
            else:
                print(f"✗ Failed to set {key}")
        else:
            if set_preference(key, value):
                print(f"✓ Set preferences.{key} = {value}")
            else:
                print(f"✗ Failed to set {key}")
        return True

    elif cmd == "add-directory" and len(args) >= 2:
        host_path = args[1]
        sandbox_name = args[2] if len(args) > 2 else None

        if add_directory(host_path, sandbox_name):
            sandbox_path = f"/workspace/{sandbox_name or Path(host_path).expanduser().name.lower()}"
            print(f"✓ Added: {host_path} → {sandbox_path}")
        else:
            print(f"✗ Directory already exists or invalid path")
        return True

    elif cmd == "remove-directory" and len(args) >= 2:
        host_path = args[1]
        if remove_directory(host_path):
            print(f"✓ Removed: {host_path}")
        else:
            print(f"✗ Directory not found: {host_path}")
        return True

    elif cmd == "reset":
        confirm = input("Reset all settings to defaults? [y/N] ")
        if confirm.lower() == 'y':
            # Keep API keys, reset everything else
            config = load_config()
            new_config = DEFAULT_CONFIG.copy()
            new_config["llm_backend"] = config.get("llm_backend")
            new_config["openai_key"] = config.get("openai_key")
            new_config["setup_complete"] = config.get("setup_complete")
            save_config(new_config)
            print("✓ Configuration reset to defaults (API keys preserved)")
        else:
            print("Cancelled.")
        return True

    else:
        print(f"Unknown config command: {cmd}")
        print("Commands: show, set, add-directory, remove-directory, reset")
        return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # CLI mode: hermit config <command>
        config_cli(sys.argv[1:])
    else:
        # Test setup
        config = ensure_setup()
        print(f"\nConfig: {json.dumps(config, indent=2)}")