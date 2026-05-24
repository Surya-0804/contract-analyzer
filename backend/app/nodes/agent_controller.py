from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.core.logging_utils import get_logger
from app.nodes.contradict import contradict_node
from app.nodes.evaluate import evaluate_node
from app.nodes.report import report_node
from app.nodes.segment import segment_node
from app.state import ContractState

logger = get_logger(__name__)

GoalStep = Callable[[ContractState], Awaitable[ContractState]]

DEFAULT_PLAN = ["segment", "evaluate", "contradict", "report"]
MAX_STEP_RETRIES = 1
MIN_CLAUSES_FOR_CONTRADICTION_CHECK = 2

STEP_HANDLERS: dict[str, GoalStep] = {
    "segment": segment_node,
    "evaluate": evaluate_node,
    "contradict": contradict_node,
    "report": report_node,
}


def build_plan(state: ContractState) -> list[str]:
    """Create a minimal plan for the current contract state."""
    plan: list[str] = []
    needs_segment = not state.get("clauses")
    needs_evaluate = needs_segment or not _has_evaluated_clauses(state)

    if needs_segment:
        plan.append("segment")
    if needs_evaluate:
        plan.append("evaluate")
    if needs_evaluate or _should_run_contradict(state):
        plan.append("contradict")
    plan.append("report")
    return plan


async def run_agent_controller(state: ContractState) -> ContractState:
    """Execute a lightweight planner/executor loop over the existing nodes."""
    goal = state.get("goal") or "analyze contract"
    plan = build_plan(state) or DEFAULT_PLAN
    state["goal"] = goal
    state["plan"] = plan
    state.setdefault("step_logs", [])
    state.setdefault("retry_counts", {})

    logger.info("agent_controller: goal=%s plan=%s", goal, " -> ".join(plan))

    for step_name in plan:
        if step_name == "contradict" and not _should_run_contradict(state):
            _log_step(state, step_name, "skipped", "Skipped because there are too few clauses.")
            continue

        state = await _run_step(state, step_name)
        if _should_retry_step(step_name, state):
            retry_count = state["retry_counts"].get(step_name, 0)
            if retry_count < MAX_STEP_RETRIES:
                state["retry_counts"][step_name] = retry_count + 1
                _log_step(
                    state,
                    step_name,
                    "retry",
                    f"Retrying {step_name} once because quality heuristics flagged the result.",
                )
                state = await _run_step(state, step_name)

    return state


async def _run_step(state: ContractState, step_name: str) -> ContractState:
    handler = STEP_HANDLERS[step_name]
    logger.info("agent_controller: running step=%s", step_name)
    next_state = await handler(state)
    _log_step(next_state, step_name, "completed", _step_summary(step_name, next_state))
    return next_state


def _has_evaluated_clauses(state: ContractState) -> bool:
    clauses = state.get("clauses", [])
    return bool(clauses) and all("risk_score" in clause for clause in clauses)


def _should_run_contradict(state: ContractState) -> bool:
    return len(state.get("clauses", [])) >= MIN_CLAUSES_FOR_CONTRADICTION_CHECK


def _should_retry_step(step_name: str, state: ContractState) -> bool:
    if step_name == "evaluate":
        return bool(state.get("llm_metadata", {}).get("evaluate", {}).get("low_confidence"))
    if step_name == "contradict":
        return bool(state.get("llm_metadata", {}).get("contradict", {}).get("unclear"))
    return False


def _step_summary(step_name: str, state: ContractState) -> str:
    if step_name == "segment":
        return f"Extracted {len(state.get('clauses', []))} clauses."
    if step_name == "evaluate":
        metadata = state.get("llm_metadata", {}).get("evaluate", {})
        if metadata.get("low_confidence"):
            return "Evaluation completed with low-confidence heuristics flagged."
        return f"Evaluated {len(state.get('clauses', []))} clauses."
    if step_name == "contradict":
        metadata = state.get("llm_metadata", {}).get("contradict", {})
        if metadata.get("unclear"):
            return "Contradiction pass completed but wording looked uncertain."
        return f"Found {len(state.get('contradictions', []))} contradictions."
    if step_name == "report":
        return f"Generated report with {len(state.get('final_report', ''))} characters."
    return "Step completed."


def _log_step(state: ContractState, step: str, status: str, detail: str) -> None:
    state.setdefault("step_logs", []).append(
        {
            "step": step,
            "status": status,
            "detail": detail,
        }
    )
