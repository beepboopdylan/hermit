"""

CaMeL-style planner for Hermit https://arxiv.org/abs/2503.18813 🐪

Key goal: The LLM generates a FIXED plan before seeing any untrusted data. Variables will be placeholders 
filled at execution. The LLM never sees file contents or command outputs during planning.

The aim is data + control flows separation.

"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional
from hermit.config import get_allowed_directories

@dataclass
class PlanStep:
    """Single step in an execution plan."""
    step_id: int
    action_json: dict
    depends_on: list[int] = field(default_factory=list)
    description: str = ""

@dataclass
class Plan:
    steps: list[PlanStep]
    description: str = ""

    def __len__(self):
        return len(self.steps)
    
def system_prompt() -> str:
    dirs = get_allowed_directories()
    workspace_lines = "\n".join(
        f"- {d['sandbox']} → user's {d['host']}"
        for d in dirs
    )
    return f"""You are Hermit's planner. Convert user requests into JSON execution plans.

            RULES:
            1. Return ONLY a JSON object. No markdown, no explanation.
            2. Each step is an action from Hermit's action set.
            3. Use $STEP{{n}} to reference the output of step n.
            4. You CANNOT see file contents. Plan generically.
            5. Keep plans minimal — fewest steps possible.
            6. For simple requests (ls, cat, etc.), return a single step.
            7. When creating code files, include useful starter content (imports, boilerplate, etc.)
            8. In file content, use \\n for newlines. Never use literal newlines inside JSON strings.

            FORMAT:
            {{
            "description": "Short summary",
            "steps": [
                {{
                "step_id": 1,
                "action": {{"action": "...", ...}},
                "depends_on": [],
                "description": "What this step does"
                }}
            ]
            }}

            AVAILABLE ACTIONS:
            - list_files: {{"action": "list_files", "path": "...", "all": false, "long": false}}
            - read_file: {{"action": "read_file", "path": "..."}}
            - create_file: {{"action": "create_file", "path": "...", "content": "..."}}
            - delete_files: {{"action": "delete_files", "path": "...", "pattern": "...", "recursive": false}}
            - move_file: {{"action": "move_file", "source": "...", "destination": "..."}}
            - create_directory: {{"action": "create_directory", "path": "..."}}
            - find_files: {{"action": "find_files", "path": "...", "pattern": "...", "file_type": "file"}}
            - organize_by_type: {{"action": "organize_by_type", "path": "..."}}
            - run_command: {{"action": "run_command", "command": "..."}}

            WORKSPACE PATHS:
            {workspace_lines}

            EXAMPLES:

            User: "show my downloads"
            {{"description": "List downloads", "steps": [{{"step_id": 1, "action": {{"action": "list_files", "path": "/workspace/downloads", "all": true, "long": true}}, "depends_on": [], "description": "List files in downloads"}}]}}

            User: "set up a python project called myapp with src and tests"
            {{"description": "Create myapp project structure", "steps": [{{"step_id": 1, "action": {{"action": "create_directory", "path": "/workspace/projects/myapp/src"}}, "depends_on": [], "description": "Create src directory"}}, {{"step_id": 2, "action": {{"action": "create_directory", "path": "/workspace/projects/myapp/tests"}}, "depends_on": [], "description": "Create tests directory"}}, {{"step_id": 3, "action": {{"action": "create_file", "path": "/workspace/projects/myapp/src/__init__.py", "content": ""}}, "depends_on": [1], "description": "Add __init__.py to src"}}, {{"step_id": 4, "action": {{"action": "create_file", "path": "/workspace/projects/myapp/tests/__init__.py", "content": ""}}, "depends_on": [2], "description": "Add __init__.py to tests"}}, {{"step_id": 5, "action": {{"action": "create_file", "path": "/workspace/projects/myapp/requirements.txt", "content": ""}}, "depends_on": [], "description": "Create requirements.txt"}}]}}
            """

def parse_plan(raw_response: str) -> Plan:
    response = raw_response.strip()

    if response.startswith("```"):
        lines = response.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        response = "\n".join(lines)

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        fixed = response
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)

        try:
            data = json.loads(fixed)
        except json.JSONDecodeError:
            # Last resort: find the outermost { }
            start = fixed.find('{')
            end = fixed.rfind('}')
            if start != -1 and end != -1:
                data = json.loads(fixed[start:end + 1])
            else:
                raise

    steps = []
    for s in data.get("steps", []):
        steps.append(PlanStep(
            step_id=s["step_id"],
            action_json=s["action"],
            depends_on=s.get("depends_on", []),
            description=s.get("description", ""),
        ))

    return Plan(steps=steps,description=data.get("description",""),)