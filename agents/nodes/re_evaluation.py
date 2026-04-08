"""
Node 8: FULL_RE_EVALUATION

This node is identical to Node 3 (RESUME_EVALUATION) but is triggered
when CRITICAL hallucinations are found. The hallucination_history is
already populated in state, so Node 3's logic will inject the constraints.

This module simply delegates to resume_evaluation.run().
"""

import logging
from agents.state import AgentState
from agents.nodes import resume_evaluation

logger = logging.getLogger(__name__)

NODE_NAME = "FULL_RE_EVALUATION"


def run(state: AgentState) -> AgentState:
    """
    Node 8: Re-run complete evaluation with anti-hallucination constraints.
    Delegates to resume_evaluation.run() — the hallucination_history in state
    will cause it to inject constraint prompts automatically.
    """
    print(f"[TRACE]   FULL_RE_EVALUATION: hallucination_history={len(state.hallucination_history)} items, "
          f"attempt={state.attempt_count}, model={state.current_model}")
    print(f"[TRACE]   Clearing previous verification state and re-running evaluation...")
    logger.info(
        f"FULL_RE_EVALUATION triggered. "
        f"Hallucination history has {len(state.hallucination_history)} items. "
        f"Attempt {state.attempt_count}."
    )

    # Clear previous verification state to avoid confusion
    state.verification_report = []
    state.supported_claims = []
    state.unsupported_claims = []
    state.severity_report = []
    state.has_critical = False
    state.has_moderate = False
    state.all_minor = False

    # Run the evaluation again (it will pick up hallucination_history from state)
    state = resume_evaluation.run(state)

    # Rename the node in path for clarity
    if state.path_taken and state.path_taken[-1] == "RESUME_EVALUATION":
        state.path_taken[-1] = NODE_NAME

    return state
