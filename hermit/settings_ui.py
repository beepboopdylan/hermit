"""

An interactive settings page for Hermit so that user does not need to rely
on memory and navigation to change settings is easier. User simply needs
to type "settings" to achieve this.

ARCHITECTURE: A state machine with 6 screens

States: screen, cursor, config
Events: keypresses (up, down, enter, space, esc, b, q)

On every keypress:
    1. keybinding handler 

"""
import time
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style
from prompt_toolkit.application import run_in_terminal

from hermit.config import load_config, get_allowed_directories, get_cgroup_config, save_config

SANDBOX_ROOT = "/home/ubuntu/sandbox-root"

MAIN = "main"
BACKEND = "backend"
SAFETY = "safety"
FOLDERS = "folders"
RESOURCES = "resources"
PREFS = "prefs"

MAIN_ITEMS = [
    (BACKEND, "LLM Backend"),
    (SAFETY, "Safety"),
    (FOLDERS, "Folders"),
    (RESOURCES, "Resource Limits"),
    (PREFS, "Preferences"),
]

state = {
    "screen": MAIN,
    "cursor": 0,
    "main_cursor": 0,
    "config": {},
    "msg": "",
}

STYLE = Style.from_dict({
    "title":    "bold",
    "pointer":  "bold fg:#ff8700",
    "item-hl":  "bold",
    "dim":      "fg:ansibrightblack",
    "value": "fg:ansicyan",
    "on":  "fg:ansibrightgreen",
    "off": "fg:ansibrightblack",
})

# ------- SCREENS -------

class Screen:
    type = ""

    def max_items(self):
        pass

    def render(self):
        raise NotImplementedError

    def on_enter(self, app):
        pass

    def on_space(self):
        pass

class MainScreen(Screen):
    type = "SETTINGS"

    def max_items(self):
        return len(MAIN_ITEMS) - 1

    def render(self):
        cfg = state["config"]

        # Building right-side values
        backend = cfg.get("llm_backend", "openai")
        backend_val = f"OpenAI ({cfg.get('openai_model','gpt-4o-mini')})" if backend == "openai" else "llama.cpp"

        directories = get_allowed_directories()
        fold_val = f"{len(directories)} mounted"

        cg = get_cgroup_config()
        res_val = f"{cg.get('memory_max_mb',512)}MB, {cg.get('cpu_quota_percent',50)}% CPU"

        safety = cfg.get("safety", {})
        safe_val = f"{sum(1 for v in safety.values() if v is True)} rules active"

        MAIN_ITEMS = [
            ("LLM Backend",    backend_val),
            ("Safety",         safe_val),
            ("Folders",        fold_val),
            ("Resource Limits",res_val),
            ("Preferences",    ""),
        ]

        out = [
            ("class:title", "  SETTINGS\n"),
            ("class:dim", "  ──────────────────────────────────\n"),
            ("", "\n"),
        ]

        for i, (label, value) in enumerate(MAIN_ITEMS):
            if i == state["cursor"]:
                out.append(("class:pointer",  "  ❯ "))
                out.append(("class:item-hl",  f"{label:<22}"))
                out.append(("class:value",    f"{value}\n"))
            else:
                out.append(("",               f"    {label:<22}"))
                out.append(("class:dim",      f"{value}\n"))

        out.append(("class:dim", "\n  ↑↓ to navigate   Q to quit\n"))
        return FormattedText(out)

class SafetyScreen(Screen):
    type = "SAFETY"
    items = [
        ("block_rm_rf", "Block rm -rf", "bool"),
        ("require_confirmation_for_delete", "Confirm deletes", "bool"),
        ("max_files_per_operation", "Max files per op", "int"),
    ]

    def max_items(self):
        return len(self.items) - 1

    def render(self):
        cfg = state["config"].get("safety", {})
        cursor = state["cursor"]

        block = cfg.get("block_rm_rf", True)
        confirm = cfg.get("require_confirmation_for_delete", True)
        max_f = cfg.get("max_files_per_operation", 100)

        items = [
            ("Block rm -rf", "[ON]" if block else "[OFF]", block),
            ("Confirm deletes", "[ON]" if confirm else "[OFF]", confirm),
            ("Max files per op", str(max_f), None),
        ]

        out = [
            ("", "\n"),
            ("class:title", "  SAFETY\n"),
            ("class:dim",   "  ──────────────────────────────────\n"),
            ("", "\n"),
        ]

        for i, (label, value, is_on) in enumerate(items):
            if is_on:
                val_style = "class:on" if is_on else "class:off"
            else:
                val_style = "class:value"
            
            if i == cursor:
                out.append(("class:pointer", "  ❯ "))
                out.append(("class:item-hl", f"{label:<28}"))
                out.append((val_style,       f"{value}\n"))
            else:
                out.append(("",              f"    {label:<28}"))
                out.append((val_style,       f"{value}\n"))

        out.append(("class:dim", "\n  'space' toggle   'enter' edit number   'esc' back\n"))
        return FormattedText(out)

    def on_enter(self, app):

        def _edit():
            raw = input("  Max files per operation: ").strip()
            if raw.isdigit():
                state["config"]["safety"]["max_files_per_operation"] = int(raw)
                save_config(state["config"])
        run_in_terminal(_edit)
        app.invalidate()

    def on_space(self):
        cfg  = state["config"]["safety"]
        keys = ["block_rm_rf", "require_confirmation_for_delete"]
        if state["cursor"] < 2:
            k = keys[state["cursor"]]
            cfg[k] = not cfg.get(k, True)
            save_config(state["config"])

class BackendScreen(Screen):
    type = "LLM BACKEND"

    items = [
        ("openai", "OpenAI"),
        ("llamacpp", "llama.cpp (offline)")
    ]

    def max_items(self):
        return len(self.items) - 1

    def render(self):
        cfg = state["config"]
        active = cfg.get("llm_backend", "openai")
        cursor = state["cursor"]

        out = [
            ("", "\n"),
            ("class:title", "  LLM BACKEND\n"),
            ("class:dim",   "  ──────────────────────────────────\n"),
            ("", "\n"),
        ]

        for i, (key, label) in enumerate(self.items):
            configured = cfg.get(f"{key}_configured", False)
            is_active = active == key

            if is_active:
                val, val_style = "✓ active", "class:on"
            elif configured:
                val, val_style = "configured", "class:value"
            else:
                val, val_style = "not configured", "class:off"

            if i == cursor:
                out.append(("class:pointer", "  ❯ "))
                out.append(("class:item-hl", f"{label:<28}"))
                out.append((val_style,       f"{val}\n"))
            else:
                out.append(("", f"    {label:<28}"))
                out.append((val_style, f"{val}\n"))

        out.append(("class:dim", "\n  ENTER to configure   B/ESC to go back\n"))

        return FormattedText(out)

    def on_enter(self, app):
        cursor = state["cursor"]

        if cursor == 0:
            def _edit():
                current = state["config"].get("openai_model", "gpt-4o-mini")
                key = input("  OpenAI API key (ENTER to skip): ").strip()
                if key and key.startswith("sk-"):
                    state["config"]["openai_key"]        = key
                    state["config"]["openai_configured"] = True
                model = input(f"  Model [{current}] (ENTER to skip): ").strip()
                if model:
                    state["config"]["openai_model"] = model
                state["config"]["llm_backend"] = "openai"
                save_config(state["config"])
            run_in_terminal(_edit)
            app.invalidate()

        elif cursor == 1:
            def _edit():
                try:
                    from pathlib import Path
                    models_dir = Path.home() / ".hermit" / "models"
                    
                    print()
                    if models_dir.exists():
                        models = list(models_dir.glob("*.gguf"))
                        if models:
                            print("  Available models:")
                            for i, m in enumerate(models):
                                print(f"    {i+1}. {m.name}")
                            print()
                        else:
                            print("  No models found in ~/.hermit/models/")
                            print("  Download one first with: hermit-download-model")
                            print()

                    current = state["config"].get("llamacpp_model_path", "")
                    if current:
                        print(f"  Current: {current}")

                    path = input("  Path to .gguf file (or ENTER to skip): ").strip()
                    if not path:
                        return
                    
                    # handle numeric selection
                    if path.isdigit():
                        idx = int(path) - 1
                        if 0 <= idx < len(models):
                            path = str(models[idx])
                        else:
                            print("  ✗ Invalid selection")
                            return

                    if not Path(path).exists():
                        print(f"  ✗ Not found: {path}")
                        return
                    state["config"]["llamacpp_model_path"] = path
                    state["config"]["llamacpp_configured"] = True
                    state["config"]["llm_backend"]         = "llamacpp"
                    save_config(state["config"])
                    print("  ✓ Saved")
                except KeyboardInterrupt:
                    return
            run_in_terminal(_edit)
            app.invalidate()

class ResourcesScreen(Screen):
    type = "Resources"

    items = [
        ("memory_max_mb", "Memory limit (MB)", "int"),
        ("cpu_quota_percent", "CPU quota (%)", "int"),
        ("pids_max", "Max PIDs", "int"),
        ("timeout_seconds", "Timeout (seconds)", "int"),
    ]

    def max_items(self):
        return len(self.items) - 1

    def render(self):
        cfg = state["config"]["cgroups"]
        max_mem = cfg.get("memory_max_mb", 512)
        cpu_quota = cfg.get("cpu_quota_percent", 50)
        max_pids = cfg.get("pids_max", 100)
        timeout_sec = cfg.get("timeout_seconds", 60)
        cursor = state["cursor"]

        out = [
            ("", "\n"),
            ("class:title", "  RESOURCE LIMITS\n"),
            ("class:dim",   "  ──────────────────────────────────\n"),
            ("", "\n"),
        ]

        for i, (key, label, _) in enumerate(self.items):
            value = str(cfg.get(key, ""))
            if i == cursor:
                out.append(("class:pointer", "  ❯ "))
                out.append(("class:item-hl", f"{label:<28}"))
                out.append(("class:value",   f"{value}\n"))
            else:
                out.append(("",              f"    {label:<28}"))
                out.append(("class:value",   f"{value}\n"))

        out.append(("class:dim", "\n  ENTER to configure   ESC to go back\n"))

        return FormattedText(out)

    def on_enter(self, app):
        key, label, _ = self.items[state["cursor"]]
        def _edit():
            raw = input(f"  {label}: ").strip()
            if raw.isdigit():
                state["config"]["cgroups"][key] = int(raw)
                save_config(state["config"])
        run_in_terminal(_edit)
        app.invalidate()

class PrefsScreen(Screen):
    type = "Preferences"

    items = [
        ("confirm_before_execute", "Confirm before execute", "bool"),
        ("dry_run_by_default", "Dry run by default", "bool")
    ]

    def max_items(self):
        return len(self.items) - 1

    def render(self):
        cfg = state["config"].get("preferences", {})
        cursor = state["cursor"]

        out = [
            ("", "\n"),
            ("class:title", "  PREFERENCES\n"),
            ("class:dim",   "  ──────────────────────────────────\n"),
            ("", "\n"),
        ]

        for i, (key, label, _) in enumerate(self.items):
            is_on = cfg.get(key, False)
            val = "[ON ]" if is_on else "[OFF]"
            val_style = "class:on" if is_on else "class:off"

            if i == cursor:
                out.append(("class:pointer", "  ❯ "))
                out.append(("class:item-hl", f"{label:<28}"))
                out.append(("class:value",   f"{val}\n"))
            else:
                out.append(("",              f"    {label:<28}"))
                out.append(("class:value",   f"{val}\n"))
   
        out.append(("class:dim", "\n  SPACE to toggle   B/ESC to go back\n"))
        return FormattedText(out)
    
    def on_space(self):
        key, _, _ = self.items[state["cursor"]]
        cfg = state["config"]["preferences"]
        cfg[key] = not cfg.get(key, False)
        save_config(state["config"])

class FoldersScreen(Screen):
    type = "Folders"

    def max_items(self):
        return max(0, len(state["config"].get("allowed_directories", [])) - 1)
    
    def render(self):
        dirs = state["config"].get("allowed_directories", [])
        cursor = state["cursor"]

        out = [
            ("", "\n"),
            ("class:title", "  FOLDER ACCESS\n"),
            ("class:dim",   "  ──────────────────────────────────\n"),
            ("", "\n"),
        ]

        if not dirs:
            out.append(("class:dim", "  No folders configured\n"))
        else:
            for i, d in enumerate(dirs):
                host = d["host"]
                sandbox = d["sandbox"]

                if i == cursor:
                    out.append(("class:pointer", "  ❯ "))
                    out.append(("class:item-hl", f"{host:<28}"))
                    out.append(("class:value",   f"{sandbox}\n"))
                else:
                    out.append(("",              f"    {host:<28}"))
                    out.append(("class:dim",     f"{sandbox}\n"))
        
        out.append(("class:dim", "\n  A to add   D to delete   B/ESC to go back\n"))
        return FormattedText(out)
    
    def _unique_sandbox_name(self, path):
        """Generate a unique sandbox name from a host path."""
        parts = path.rstrip("/").split("/")
        name = parts[-1].lower()
        existing = {d["sandbox"] for d in state["config"].get("allowed_directories", [])}
        if f"/workspace/{name}" not in existing:
            return name
        # collision — prepend parent folder: e.g. "maya-downloads"
        if len(parts) >= 2:
            name = f"{parts[-2]}-{parts[-1]}".lower()
        if f"/workspace/{name}" not in existing:
            return name
        # still collides — append a number
        base = name
        n = 2
        while f"/workspace/{name}" in existing:
            name = f"{base}-{n}"
            n += 1
        return name

    def add(self, app):
        def _edit():
            path = input("  Host path (e.g. ~/Music): ").strip()
            if not path:
                return
            from hermit.config import add_directory, remove_directory
            from hermit.mounts import mount_dr
            sandbox_name = self._unique_sandbox_name(path)
            if add_directory(path, sandbox_name):
                state["config"] = load_config()
                result = mount_dr(path, f"/workspace/{sandbox_name}")
                if result:
                    state["mounted_paths"].append(result)
                else:
                    # mount failed — roll back config entry
                    remove_directory(path)
                    state["config"] = load_config()
                    print("  ✗ Mount failed — check that the path exists")
            else:
                print("  ✗ Already added")
        run_in_terminal(_edit)
        app.invalidate()

    def delete(self, app):
        dirs = state["config"].get("allowed_directories", [])
        if not dirs:
            return
        d = dirs[state["cursor"]]
        def _confirm():
            confirm = input(f"  Delete {d['host']}? (y/N): ").strip().lower()
            if confirm == "y":
                from hermit.config import remove_directory
                from hermit.mounts import unmount_dr
                unmount_dr(d["sandbox"])
                # remove from mounted_paths
                sandbox_full = f"{SANDBOX_ROOT}{d['sandbox']}"
                if sandbox_full in state["mounted_paths"]:
                    state["mounted_paths"].remove(sandbox_full)
                remove_directory(d["host"])
                state["config"] = load_config()
                state["cursor"] = max(0, state["cursor"] - 1)
        run_in_terminal(_confirm)
        app.invalidate()

def go(screen):
    state["screen"] = screen    
    state["cursor"] = 0
    state["msg"] = ""

def move(delta, max_idx):
    state["cursor"] = max(0, min(max_idx, state["cursor"] + delta))

def set_msg(msg):
    state["msg"] = msg

# ------- RENDERING FUNCTIONS --------

def render():
    screen = SCREENS.get(state["screen"])
    if screen:
        return screen.render()
    return FormattedText([("", "unknown screen\n")])

SCREENS = {
    MAIN: MainScreen(),
    BACKEND: BackendScreen(),
    SAFETY: SafetyScreen(),
    FOLDERS: FoldersScreen(),
    RESOURCES: ResourcesScreen(),
    PREFS: PrefsScreen(),
}

# ------- KEY BINDERS -------

kb = KeyBindings()

@kb.add("q")
def _quit(event):
    event.app.exit()

@kb.add("down")
def _down(event):
    screen = SCREENS.get(state["screen"])
    if screen:
        move(1, screen.max_items())

@kb.add("up")
def _up(event):
    screen = SCREENS.get(state["screen"])
    if screen:
        move(-1, screen.max_items())

@kb.add("enter")
def _enter(event):
    if state["screen"] == MAIN:
        state["main_cursor"] = state["cursor"]
        go(MAIN_ITEMS[state["cursor"]][0])
    else:
        screen = SCREENS.get(state["screen"])
        if screen:
            screen.on_enter(event.app)

@kb.add("escape")
@kb.add("b")
def _back(event):
    if state["screen"] != MAIN:
        go(MAIN)
        state["cursor"] = state["main_cursor"]

@kb.add("a")
def _add(event):
    if state["screen"] == FOLDERS:
        SCREENS[FOLDERS].add(event.app)

@kb.add("d")
def _delete(event):
    if state["screen"] == FOLDERS:
        SCREENS[FOLDERS].delete(event.app)

@kb.add("space")
def _space(event):
    screen = SCREENS.get(state["screen"])
    if screen:
        screen.on_space()

# ------- RUNNING THE SETTINGS PAGE -------

def run_settings(mounted_paths: list = None):
    state["screen"] = MAIN
    state["cursor"] = 0
    state["config"] = load_config()
    state["msg"] = ""
    state["mounted_paths"] = mounted_paths or []
    
    time.sleep(0.1)

    app = Application(
        layout=Layout(Window(FormattedTextControl(render, show_cursor=False))),
        key_bindings=kb,
        style=STYLE,
        full_screen=True,
    )
    def pre_run():
        import sys, termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)

    app.run(pre_run=pre_run)