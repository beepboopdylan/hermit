"""
Structured actions for Hermit.
LLM proposes actions, we render them to shell commands.
"""

from dataclasses import dataclass
from typing import Optional
import json

@dataclass
class Action:
    """Base action that LLM can propose."""
    action: str
    
    def render(self) -> str:
        """Convert to shell command. Override in subclasses."""
        raise NotImplementedError
    
    def describe(self) -> str:
        """Human-readable description."""
        raise NotImplementedError

@dataclass
class ListFiles(Action):
    action: str = "list_files"
    path: str = "."
    all: bool = False
    long: bool = False
    
    def render(self) -> str:
        flags = ""
        if self.all:
            flags += "a"
        if self.long:
            flags += "l"
        if flags:
            return f"ls -{flags} {self.path}"
        return f"ls {self.path}"
    
    def describe(self) -> str:
        return f"List files in {self.path}"
    
@dataclass
class ReadFile(Action):
    action: str = "read_file"
    path: str = ""
    
    def render(self) -> str:
        return f"cat {self.path}"
    
    def describe(self) -> str:
        return f"Read contents of {self.path}"

@dataclass  
class CreateFile(Action):
    action: str = "create_file"
    path: str = ""
    content: str = ""
    
    def render(self) -> str:
        # Escape content for shell
        escaped = self.content.replace("'", "'\\''")
        return f"echo '{escaped}' > {self.path}"
    
    def describe(self) -> str:
        return f"Create file {self.path}"

@dataclass
class DeleteFiles(Action):
    action: str = "delete_files"
    path: str = ""
    pattern: Optional[str] = None
    recursive: bool = False
    
    def render(self) -> str:
        if self.pattern:
            if self.recursive:
                return f"find {self.path} -name '{self.pattern}' -delete"
            return f"rm {self.path}/{self.pattern}"
        if self.recursive:
            return f"rm -r {self.path}"
        return f"rm {self.path}"
    
    def describe(self) -> str:
        if self.pattern:
            return f"Delete files matching {self.pattern} in {self.path}"
        return f"Delete {self.path}"
    
@dataclass
class MoveFile(Action):
    action: str = "move_file"
    source: str = ""
    destination: str = ""
    
    def render(self) -> str:
        return f"mv {self.source} {self.destination}"
    
    def describe(self) -> str:
        return f"Move {self.source} to {self.destination}"

@dataclass
class OrganizeByType(Action):
    action: str = "organize_by_type"
    path: str = "."
    
    def render(self) -> str:
        # Proper logic that doesn't move folders into each other
        return f"""cd {self.path} && 
mkdir -p images documents audio video archives other &&
for f in *.jpg *.jpeg *.png *.gif *.webp; do [ -f "$f" ] && mv "$f" images/; done 2>/dev/null;
for f in *.pdf *.doc *.docx *.txt *.md; do [ -f "$f" ] && mv "$f" documents/; done 2>/dev/null;
for f in *.mp3 *.wav *.flac; do [ -f "$f" ] && mv "$f" audio/; done 2>/dev/null;
for f in *.mp4 *.mov *.avi; do [ -f "$f" ] && mv "$f" video/; done 2>/dev/null;
for f in *.zip *.tar *.gz; do [ -f "$f" ] && mv "$f" archives/; done 2>/dev/null;
true"""
    
    def describe(self) -> str:
        return f"Organize files in {self.path} by type"

@dataclass
class CreateDirectory(Action):
    action: str = "create_directory"
    path: str = ""
    
    def render(self) -> str:
        return f"mkdir -p {self.path}"
    
    def describe(self) -> str:
        return f"Create directory {self.path}"

@dataclass
class FindFiles(Action):
    action: str = "find_files"
    path: str = "."
    pattern: Optional[str] = None
    file_type: Optional[str] = None  # "file" or "directory"
    
    def render(self) -> str:
        cmd = f"find {self.path}"
        if self.file_type == "file":
            cmd += " -type f"
        elif self.file_type == "directory":
            cmd += " -type d"
        if self.pattern:
            cmd += f" -name '{self.pattern}'"
        return cmd

    def describe(self) -> str:
        return f"Find files matching {self.pattern} in {self.path}"

@dataclass
class RunCommand(Action):
    """Fallback for commands we don't have a specific action for."""
    action: str = "run_command"
    command: str = ""
    
    def render(self) -> str:
        return self.command
    
    def describe(self) -> str:
        return f"Run: {self.command}"

# Map action names to classes
ACTION_MAP = {
    "list_files": ListFiles,
    "read_file": ReadFile,
    "create_file": CreateFile,
    "delete_files": DeleteFiles,
    "move_file": MoveFile,
    "create_directory": CreateDirectory,
    "find_files": FindFiles,
    "run_command": RunCommand,
    "organize_by_type": OrganizeByType,
}

def parse_action(json_str: str) -> Action:
    try:
        data = json.loads(json_str)

        action_type = data.get("action", "run_command")
        action_class = ACTION_MAP.get(action_type, RunCommand)

        valid_fields = {k: v for k, v in data.items() 
                       if k in action_class.__dataclass_fields__}
        
        return action_class(**valid_fields)
    except (json.JSONDecodeError, TypeError) as e:
        return RunCommand(command=json_str)
    
if __name__ == "__main__":
    # Test
    test_cases = [
        '{"action": "list_files", "path": ".", "all": true, "long": true}',
        '{"action": "delete_files", "path": ".", "pattern": "*.log", "recursive": true}',
        '{"action": "read_file", "path": "welcome.txt"}',
        '{"action": "create_directory", "path": "new_folder"}',
    ]
    
    print("Action parsing tests:\n")
    for json_str in test_cases:
        action = parse_action(json_str)
        print(f"JSON: {json_str}")
        print(f"  → {action.describe()}")
        print(f"  → {action.render()}\n")
