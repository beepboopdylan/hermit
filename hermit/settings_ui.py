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

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style

from hermit.config import load_config, get_allowed_directories, get_cgroup_config, save_config

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
    fn = RENDERERS.get(state["screen"], None)
    if fn:
        return fn()
    return FormattedText([("", "unknown screen\n")])

def render_main():
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

    out.append(("class:dim", "\n  '↑↓' navigate   'q' to quit\n"))
    return FormattedText(out)

def render_backend():
    return FormattedText([
        ("", "\n"),
        ("class:title", "  LLM BACKEND\n"),
        ("class:dim",   "  ──────────────────────────────────\n"),
        ("", "\n"),
        ("class:dim",   "  (coming soon)\n"),
        ("", "\n"),
        ("class:dim",   "  'esc' to go back\n"),
    ])

def render_safety():
    cfg = state["config"].get("safety", {})
    cursor = state["cursor"]

    block = cfg.get("block_rm_rf", True)
    confirm = cfg.get("require_confirmation_for_delete", True)
    max_f = cfg.get("max_files_per_operation", 100)

    items = [
        ("Block rm -rf", "[ON ]" if block else "[OFF]", block),
        ("Confirm deletes", "[ON ]" if confirm else "[OFF]", confirm),
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

def render_folders():
    return FormattedText([
        ("", "\n"),
        ("class:title", "  FOLDER ACCESS\n"),
        ("class:dim",   "  ──────────────────────────────────\n"),
        ("", "\n"),
        ("class:dim",   "  (coming soon)\n"),
        ("", "\n"),
        ("class:dim",   "  'esc' to go back\n"),
    ])

def render_resources():
    return FormattedText([
        ("", "\n"),
        ("class:title", "  MANAGE RESOURCES\n"),
        ("class:dim",   "  ──────────────────────────────────\n"),
        ("", "\n"),
        ("class:dim",   "  (coming soon)\n"),
        ("", "\n"),
        ("class:dim",   "  'esc' to go back\n"),
    ])

def render_prefs():
    return FormattedText([
        ("", "\n"),
        ("class:title", "  PREFERENCES\n"),
        ("class:dim",   "  ──────────────────────────────────\n"),
        ("", "\n"),
        ("class:dim",   "  (coming soon)\n"),
        ("", "\n"),
        ("class:dim",   "  'esc' to go back\n"),
    ])

RENDERERS = {
    MAIN: render_main,
    BACKEND: render_backend,
    SAFETY: render_safety,
    FOLDERS: render_folders,
    RESOURCES: render_resources,
    PREFS: render_prefs,
}

# ------- KEY BINDERS -------

kb = KeyBindings()

@kb.add("q")
def _quit(event):
    event.app.exit()

@kb.add("down")
def _down(event):
    move(1, len(MAIN_ITEMS) - 1)

@kb.add("up")
def _up(event):
    move(-1, len(MAIN_ITEMS) - 1)

@kb.add("enter")
def _enter(event):
    if state["screen"] == MAIN:
        state["main_cursor"] = state["cursor"]
        go(MAIN_ITEMS[state["cursor"]][0])
    elif state["screen"] == SAFETY and state["cursor"] == 2:
        def _edit():
            raw = input("  Max files per operation: ").strip()
            if raw.isdigit():
                state["config"]["safety"]["max_files_per_operation"] = int(raw)
                save_config(state["config"])
        event.app.run_in_terminal(_edit)

@kb.add("space")
def _space(event):
    if state["screen"] != SAFETY:
        return
    cfg  = state["config"]["safety"]
    keys = ["block_rm_rf", "require_confirmation_for_delete"]
    if state["cursor"] < 2:
        k = keys[state["cursor"]]
        cfg[k] = not cfg.get(k, True)
        save_config(state["config"])

@kb.add("escape")
@kb.add("b")
def _back(event):
    if state["screen"] != MAIN:
        go(MAIN)
        state["cursor"] = state["main_cursor"]

@kb.add("space")
def _space(event):
    if state["screen"] != SAFETY:
        return
    cfg  = state["config"]["safety"]
    keys = ["block_rm_rf", "require_confirmation_for_delete"]
    if state["cursor"] < 2:
        k = keys[state["cursor"]]
        cfg[k] = not cfg.get(k, True)
        save_config(state["config"])

def run_settings():
    state["screen"] = MAIN
    state["cursor"] = 0
    state["config"] = load_config()
    state["msg"] = ""

    app = Application(
        layout=Layout(Window(FormattedTextControl(render, show_cursor=False))),
        key_bindings=kb,
        style=STYLE,
        full_screen=True,
    )
    app.run()

run_settings()