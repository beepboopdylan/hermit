"""

The data flow half of CaMeL's control/data separation:
- The plan (control) was fixed by the planner before any data was seen
- The executor fills in $STEP variables with real outputs (data)
- Adaptation on failure is RULE-BASED only — no LLM calls

Data provenance: every variable tracks which step produced it.

"""

import json
from dataclasses import dataclass, field
from typing import Optional, Callable

from hermit.actions import parse_action
from hermit.policy import check_command, RiskLevel
from hermit.planner import Plan
from hermit import audit, ui

@dataclass
class StepResult:
    """Result of executing one plan step."""
    step_id: int
    command: str
    output: str
    success: bool
    risk: str
    skipped: bool = False
    error: Optional[str] = None

@dataclass
class ExecutionContext:
    """Tracks state during plan execution"""

    results: dict = field(default_factory=dict)
    variables: dict = field(default_factory=dict)

    def record(self, step_id: int, result: StepResult):
        self.results[step_id] = result

        if result.success:
            self.variables[f"$STEP{step_id}"] = result.output.strip()

    def substitute(self, text: str) -> str:
        """Replace $STEP{n} placeholders with actual outputs."""
        res = text
        for var, val in self.variables.items():
            res = res.replace(var, val)

        return res
    
    def deps_satisfied(self, depends_on: list) -> tuple:
        """Check if all dependency steps succeeded."""
        for dep_id in depends_on:
            if dep_id not in self.results:
                return False, f"Step {dep_id} hasn't run yet"
            if not self.results[dep_id].success:
                return False, f"Step {dep_id} failed"
        return True, ""
    

# deal with failure
def try_adapt(command: str, error_output: str) -> Optional[str]:
    if "No such file or directory" in error_output:
        # Extract path, mkdir its parent
        for token in reversed(command.split()):
            if "/" in token and not token.startswith("-"):
                parent = "/".join(token.split("/")[:-1])
                if parent:
                    return f"mkdir -p {parent}"
                
    if "File exists" in error_output:
        return None  # Already done, not really an error

    if "Permission denied" in error_output:
        return None  # Can't fix inside sandbox

    return None

def _looks_like_error(command: str, output: str) -> bool:
    """Heuristic: does the output look like an error?"""

    passthrough = ["find", "ls", "grep", "cat", "wc", "head", "tail"]
    cmd_base = command.strip().split()[0] if command.strip() else ""

    if cmd_base in passthrough:
        return False

    error_signals = [
        "No such file", "Permission denied", "not found",
        "cannot ", "fatal:", "Error:",
    ]
    return any(sig in output for sig in error_signals)

def execute_plan(plan: Plan, execute_fn: Callable[[str], str], approve_fn: Callable[[str], bool], step_by_step: bool,) -> list:
    """
    Execute a plan step by step
    """

    context = ExecutionContext()
    results = []

    ui.info(plan.description)
    print(f"  {ui.dim(f'{len(plan)} steps')}\n")

    for i, step in enumerate(plan.steps):
        label = f"[{i + 1}/{len(plan)}]"

        # dependency check
        deps_ok, reason = context.deps_satisfied(step.depends_on)
        if not deps_ok:
            result = StepResult(
                step_id=step.step_id, command="", output="",
                success=False, risk="skipped", skipped=True,
                error=f"Dependency failed: {reason}",
            )
            context.record(step.step_id, result)
            results.append(result)
            print(f"  {ui.dim(label)} {ui.dim(step.description)} {ui.dim('— skipped')}")
            continue

        # build command
        action_str = context.substitute(json.dumps(step.action_json))
        action = parse_action(action_str)
        command = action.render()

        policy = check_command(command)
        audit.log_policy_check(command, policy.allowed, policy.risk.value, policy.reason)

        if not policy.allowed:
            result = StepResult(
                step_id=step.step_id, command=command, output="",
                success=False, risk="blocked", error=policy.reason,
            )

            context.record(step.step_id, result)
            results.append(result)
            print(f"  {ui.red('✗')} {label} {step.description}")
            ui.risk_display("blocked", policy.reason)
            continue
        
        ui.info(step.description)
        ui.info(f"${command}")

        if step_by_step or policy.risk == RiskLevel.HIGH:
            ui.risk_display(policy.risk.value, policy.reason)
            if not approve_fn(policy.risk.value):
                result = StepResult(
                    step_id=step.step_id, command=command, output="",
                    success=False, risk="high", skipped=True, error="User cancelled",
                )
                context.record(step.step_id, result)
                results.append(result)
                continue
        
        output = execute_fn(command)
        audit.log_execution(command, output, True)

        success = not _looks_like_error(command, output)

        if not success:
            fixed_command = try_adapt(command, output)
            if fixed_command:
                print(f"    {ui.yellow('↻')} Fixing: {ui.dim(fixed_command)}")
                execute_fn(fixed_command)
                output = execute_fn(command)  # Retry
                success = not _looks_like_error(command, output)

        result = StepResult(
            step_id=step.step_id, command=command, output=output,
            success=success, risk=policy.risk.value,
            error=output.strip() if not success else None,
        )
        context.record(step.step_id, result)
        results.append(result)

        if success:
            _print_output(output)
        else:
            ui.error(result.error)

    _print_summary(results)
    return results

def _print_output(output: str):
    """Print command output, truncated if long."""
    text = output.strip()
    if not text:
        print(f"    {ui.green('✓')}")
        return

    lines = text.split("\n")
    print(f"    {ui.green('✓')}")
    if len(lines) <= 5:
        for line in lines:
            print(f"    {ui.dim(line)}")
    else:
        for line in lines[:3]:
            print(f"    {ui.dim(line)}")
        print(f"    {ui.dim(f'... +{len(lines) - 3} more lines')}")


def _print_summary(results: list):
    """Print execution summary."""
    succeeded = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)

    parts = [f"{ui.green(str(succeeded))} done"]
    if failed:
        parts.append(f"{ui.red(str(failed))} failed")
    if skipped:
        parts.append(f"{ui.dim(str(skipped))} skipped")

    print(f"\n  {', '.join(parts)}")


