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

MAIN = "main"
BACKEND = "backend"
SAFETY = "safety"
FOLDERS = "folders"
RESOURCES = "resources"
PREFS = "preferences"

MAIN_ITEMS = [
    "LLM Backend",
    "Safety",
    "Folders",
    "Resource Limits",
    "Preferences",
]

state = {
    "screen": MAIN,
    "cursor": 0,
    "config": {},
    "msg": "",
}

def go(screen):
    state["screen"] = screen
    state["cursor"] = 0
    state["msg"] = ""

def move(delta, max_idx):
    state["cursor"] = max(0, min(max_idx, state["cursor"] + delta))

def set_msg(msg):
    state["msg"] = msg

def render():
    if state["screen"] == MAIN:
        return render_main()
    return FormattedText([("", "unknown screen\n")])

def render_main():
    out = [
        ("", "\n"),
        ("", "  SETTINGS\n"),
        ("", "  ──────────────────────────────────\n"),
        ("", "\n"),
    ]

    for i, label in enumerate(MAIN_ITEMS):
        if i == state["cursor"]:
            out.append(("", f"  ❯ {label}\n"))
        else:
            out.append(("", f"    {label}\n"))
    
    out.append(("", "\n  ↑↓ navigate   q quit\n"))
    return FormattedText(out)

kb = KeyBindings()

@kb.add("q")
def _quit(event):
    event.app.exit()

def run_settings():
    state["screen"] = MAIN
    state["cursor"] = 0
    state["config"] = {}
    state["msg"] = ""

    app = Application(
        layout=Layout(Window(FormattedTextControl(render))),
        key_bindings=kb,
        full_screen=True,
    )
    app.run()

run_settings()