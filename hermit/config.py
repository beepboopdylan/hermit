import json
import os
from pathlib import Path
import subprocess
import sys 

def _check_llamacpp_installed() -> bool:
    """Check if llama-cpp-python is installed."""
    try:
        import llama_cpp
        return True
    except ImportError:
        return False

def _install_llamacpp() -> bool:
    """Install llama-cpp-python. Returns True if successful."""
    from hermit import ui

    print()
    ui.info("Installing llama-cpp-python...")
    print()
    
    try:
        # Try pre-built CPU wheel first (fast)
        result = subprocess.run(
            [
                sys.executable, "-m", "pip", "install", 
                "llama-cpp-python",
                "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cpu"
            ]
        )
        
        if result.returncode == 0:
            print()
            ui.success("Installed successfully")
            return True
        
        print()
        ui.warning("Pre-built wheel failed, trying source build...")
        ui.info("(This can take 5-10 minutes)")
        print()
        
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "llama-cpp-python"]
        )
        
        if result.returncode == 0:
            print()
            ui.success("Installed successfully (built from source)")
            return True
        else:
            print()
            ui.error("Installation failed")
            return False
            
    except Exception as e:
        ui.error(f"Installation failed: {e}")
        return False

CONFIG_DIR = Path.home() / ".hermit"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    # LLM settings
    "llm_backend": "openai",

    # OpenAI settings
    "openai_key": None,
    "openai_model": "gpt-4o-mini",

    # llama.cpp settings
    "llamacpp_model_path": None,
    "llamacpp_n_ctx": 4096,
    "llamacpp_n_gpu_layers": -1,  # -1 = all layers on GPU, 0 = CPU only

    # Setup flags
    "setup_complete": False,
    "openai_configured": False,
    "llamacpp_configured": False,

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

RECOMMENDED_MODELS = [
    {
        "name": "Qwen2.5-Coder-3B-Instruct",
        "filename": "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf",
        "size_mb": 2000,
        "ram_required": "4GB",    
    },
    {
        "name": "Qwen2.5-Coder-7B-Instruct", 
        "filename": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "size_mb": 4700,
        "ram_required": "8GB",
    },
]

MODELS_DIR = CONFIG_DIR / "models"

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

def get_models_dir() -> Path:
    """Get models directory, create if needed."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR

def get_active_backend() -> str:
    """Get currently active backend name."""
    config = load_config()
    return config.get("llm_backend", "openai")

def set_active_backend(backend: str) -> bool:
    """Switch active backend. Returns False if backend not configured."""
    if backend not in ["openai", "llamacpp"]:
        return False
    
    config = load_config()

    if backend == "openai" and not config.get("openai_configured"):
        return False
    if backend == "llamacpp" and not config.get("llamacpp_configured"):
        return False
    
    config["llm_backend"] = backend
    save_config(config)
    return True

def get_available_backends() -> list:
    """Return list of configured backends."""
    config = load_config()
    available = []

    if config.get("openai_configured"):
        available.append("openai")
    if config.get("llamacpp_configured"):
        available.append("llamacpp")

    return available

def show_config():
    """Display current configuration in a readable format."""
    config = load_config()

    print("\n" + "=" * 50)
    print("  HERMIT CONFIGURATION")
    print("=" * 50)

    print("\n[LLM Backend]")
    backend = config.get("llm_backend", "openai")
    print(f"  Active: {backend}")
    available = get_available_backends()
    print(f"  Available: {', '.join(available) if available else 'none'}")

    # OpenAI setting
    print("\n[OpenAI]")
    if config.get("openai_configured"):
        key = config.get('openai_key', '')
        masked = key[:7] + '...' + key[-4:] if key and len(key) > 15 else '(not set)'
        print(f"  Configured")
        print(f"  Key: {masked}")
        print(f"  Model: {config.get('openai_model', 'gpt-4o-mini')}")
    else:
        print(f"  Not configured")

    # llamacpp
    print("\n[llama.cpp]")
    if config.get("llamacpp_configured"):
        model_path = config.get('llamacpp_model_path', '')
        model_name = Path(model_path).name if model_path else '(not set)'
        print(f"  ✓ Configured")
        print(f"  Model: {model_name}")
    else:
        print(f"  ✗ Not configured")

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

    config = load_config()

    # Ask which backend(s) to configure
    print("  Which LLM backend do you want to use?")
    print()
    print("    1. OpenAI (online, needs API key)")
    print("    2. llama.cpp (offline, runs locally)")
    print("    3. Both")
    print()

    while True:
        choice = input("  Select (1-3): ").strip()
        if choice in ['1', '2', '3']:
            break
        print("  Please enter 1, 2, or 3")

    if choice in ['1', '3']:
        print()
        print(f"  Get your API key from: {ui.dim('https://platform.openai.com/api-keys')}")
        print()

        while True:
            key = input("  OpenAI API key: ").strip()
            if key.startswith("sk-") and len(key) > 20:
                break
            if not key and choice == '3':
                print("  Skipping OpenAI...")
                break
            ui.error("Invalid key format. Should start with 'sk-'")
        
        if key:
            config["openai_key"] = key
            config["openai_configured"] = True
            ui.success("OpenAI configured")
        
    if choice in ['3', '2']:
        print()
        print(f"  {ui.bold('llama.cpp Setup (Offline Mode)')}")
        print()

        if _check_llamacpp_installed():
            ui.success("llama-cpp-python is installed")
        else:
            print("  llama-cpp-python not found.")
            install = input("  Install it now? (Y/n): ").strip().lower()

            if install in ('', 'y', 'yes'):
                if not _install_llamacpp():
                    print()
                    print("  You can install manually later:")
                    print("    pip install llama-cpp-python")
                    print()
                    if choice == '2':
                        print("  Setup incomplete. Run 'hermit' again after installing.")
                        return config
                    else:
                        print("  Continuing with OpenAI only...")
                        config["llm_backend"] = "openai"
                        config["setup_complete"] = True
                        save_config(config)
                        return config
            else:
                print()
                print("  Skipping llama.cpp setup.")
                if choice == '2':
                    print("  Run 'hermit' again after installing llama-cpp-python.")
                    return config
                else:
                    config["llm_backend"] = "openai"
        
        print()
        print("  Available models:")
        for i, m in enumerate(RECOMMENDED_MODELS, 1):
            print(f"    {i}. {m['name']} (~{m['size_mb']}MB, needs {m['ram_required']})")
        print(f"    {len(RECOMMENDED_MODELS)+1}. Custom path")
        print()

        while True:
            model_choice = input(f"  Select (1-{len(RECOMMENDED_MODELS)+1}): ").strip()
            try:
                idx = int(model_choice)
                if 1 <= idx <= len(RECOMMENDED_MODELS):
                    # Download model
                    model_info = RECOMMENDED_MODELS[idx-1]
                    model_path = _download_model(model_info)
                    if model_path:
                        config["llamacpp_model_path"] = model_path
                        config["llamacpp_configured"] = True
                    break
                elif idx == len(RECOMMENDED_MODELS) + 1:
                    path = input("  Path to .gguf file: ").strip()
                    if Path(path).exists():
                        config["llamacpp_model_path"] = path
                        config["llamacpp_configured"] = True
                        break
                    ui.error("File not found")
            except ValueError:
                pass

    
    if config.get("openai_configured") and config.get("llamacpp_configured"):
        print()
        default = input("  Default backend? (1=OpenAI, 2=llama.cpp) [1]: ").strip()
        config["llm_backend"] = "llamacpp" if default == "2" else "openai"
    elif config.get("openai_configured"):
        config["llm_backend"] = "openai"
    elif config.get("llamacpp_configured"):
        config["llm_backend"] = "llamacpp"
 
    config["setup_complete"] = True
    save_config(config)
    
    print()
    ui.success("Setup complete!")
    ui.info(f"Config saved to {ui.dim(str(CONFIG_FILE))}")
    print()
    
    return config

def _download_model(model_info: dict) -> str:
    """Download a model, return path."""
    import urllib.request
    import sys
    from hermit import ui
    
    models_dir = get_models_dir()
    model_path = models_dir / model_info["filename"]
    
    if model_path.exists():
        ui.info(f"Model already downloaded: {model_info['filename']}")
        return str(model_path)
    
    ui.info(f"Downloading {model_info['name']} (~{model_info['size_mb']}MB)...")
    print()
    
    def progress(block_num, block_size, total_size):
        current = block_num * block_size
        ui.download_progress(current, total_size)
    
    try:
        urllib.request.urlretrieve(model_info["url"], model_path, progress)
        print()  # Newline after progress bar
        ui.success(f"Downloaded to {model_path}")
        return str(model_path)
    except Exception as e:
        print()
        ui.error(f"Download failed: {e}")
        return None
    
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