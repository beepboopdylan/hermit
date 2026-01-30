import json
import os
import shutil
import subprocess
from pathlib import Path

CONFIG_DIR = Path.home() / ".hermit"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    # LLM settings
    "llm_backend": None,  # "ollama" or "openai"
    "ollama_model": "tinyllama",
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

# ============================================================
# Directory Management
# ============================================================

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

# ============================================================
# Preferences Management
# ============================================================

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

# ============================================================
# Safety Settings Management
# ============================================================

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

# ============================================================
# Config Display
# ============================================================

def show_config():
    """Display current configuration in a readable format."""
    config = load_config()

    print("\n" + "=" * 50)
    print("  HERMIT CONFIGURATION")
    print("=" * 50)

    # LLM Settings
    print("\n[LLM Settings]")
    print(f"  Backend: {config.get('llm_backend', 'not configured')}")
    if config.get('llm_backend') == 'openai':
        key = config.get('openai_key', '')
        masked = key[:7] + '...' + key[-4:] if key and len(key) > 15 else '***'
        print(f"  OpenAI Key: {masked}")
        print(f"  OpenAI Model: {config.get('openai_model', 'gpt-4o-mini')}")
    elif config.get('llm_backend') == 'ollama':
        print(f"  Ollama Model: {config.get('ollama_model', 'tinyllama')}")

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

    print("\n" + "=" * 50)
    print(f"  Config file: {CONFIG_FILE}")
    print("=" * 50 + "\n")

def is_ollama_installed() -> bool:
    return shutil.which("ollama") is not None

def is_ollama_running() -> bool:
    """Check if ollama server is running."""
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except:
        return False

def install_ollama():
    """Install ollama."""
    print("   Installing Ollama...")
    result = subprocess.run(
        "curl -fsSL https://ollama.ai/install.sh | sh",
        shell=True,
    )
    if result.returncode != 0:
        print("   Failed to install Ollama")
        print(f"   {result.stderr.decode()}")
        return False
    return True

def pull_ollama_model(model: str):
    """Download an ollama model."""
    print(f"   Downloading {model} (this may take a few minutes)...")
    result = subprocess.run(
        ["ollama", "pull", model],
        capture_output=False  # Show progress
    )
    return result.returncode == 0

def start_ollama():
    """Start ollama server in background."""
    if not is_ollama_running():
        print("   Starting Ollama server...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        # Wait for it to start
        import time
        for _ in range(10):
            if is_ollama_running():
                return True
            time.sleep(1)
        return False
    return True

def first_run_setup() -> dict:
    """Interactive first-run setup. Returns config."""
    print("\n🦀 Welcome to Hermit!")
    print("   First-time setup required.\n")
    print("   Get your API key from: https://platform.openai.com/api-keys\n")

    config = load_config()

    while True:
        key = input("   OpenAI API key: ").strip()
        if key.startswith("sk-") and len(key) > 20:
            break
        print("   Invalid key format. Should start with 'sk-'")

    config["llm_backend"] = "openai"
    config["openai_key"] = key
    config["setup_complete"] = True
    save_config(config)

    print("\n   OpenAI configured!")
    print("   Config saved to ~/.hermit/config.json\n")
    return config

def ensure_setup() -> dict:
    """Make sure setup is complete. Returns config."""
    config = load_config()

    if not config["setup_complete"]:
        return first_run_setup()

    return config


# ============================================================
# CLI Interface
# ============================================================

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