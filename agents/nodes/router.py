import time
import logging

from agents.state import AgentState
from config import settings

logger = logging.getLogger(__name__)

NODE_NAME = "ROUTER"

# Routing decisions
ROUTE_FINAL = "FINAL_OUTPUT"
ROUTE_PATCH = "PATCH_AND_RECALCULATE"
ROUTE_RE_EVALUATE = "FULL_RE_EVALUATION"
ROUTE_ESCALATION = "ESCALATION"


def run(state: AgentState) -> str:
    """
    Node 6: Decide next action based on severity and attempt count.
    Pure logic — no LLM call.

    Returns the name of the next node to execute.
    """
    start = time.time()
    state.current_node = NODE_NAME
    state.path_taken.append(NODE_NAME)

    max_attempts = settings.max_evaluation_attempts
    decision = ""
    reason = ""

    print(f"[TRACE]   ROUTER inputs: attempt_count={state.attempt_count}, max_attempts={max_attempts}, "
          f"all_minor={state.all_minor}, has_critical={state.has_critical}, has_moderate={state.has_moderate}")

    if state.all_minor:
        decision = ROUTE_FINAL
        reason = "All unsupported claims are MINOR"
        state.confidence = "medium"
        state.status = "accepted_with_disclaimer"

    elif state.attempt_count >= max_attempts:
        # Max attempts reached — escalate
        decision = ROUTE_ESCALATION
        reason = f"Max attempts ({max_attempts}) reached with unresolved hallucinations"
        # Add all unsupported claims to history
        for claim in state.unsupported_claims:
            claim_text = claim.get("claim", str(claim))
            if claim_text not in state.hallucination_history:
                state.hallucination_history.append(claim_text)

    elif state.has_critical:
        decision = ROUTE_RE_EVALUATE
        reason = "Critical hallucination detected, triggering full re-evaluation"
        # Add ALL unsupported claims to history
        for claim in state.unsupported_claims:
            claim_text = claim.get("claim", str(claim))
            if claim_text not in state.hallucination_history:
                state.hallucination_history.append(claim_text)

    elif state.has_moderate:
        decision = ROUTE_PATCH
        reason = "Moderate hallucination detected, triggering patch"
        # Add moderate and critical claims to history
        for item in state.severity_report:
            if item.get("severity") in ("MODERATE", "CRITICAL"):
                claim_text = item.get("claim", str(item))
                if claim_text not in state.hallucination_history:
                    state.hallucination_history.append(claim_text)

    else:
        # Fallback — should not happen, but treat as minor
        decision = ROUTE_FINAL
        reason = "No severity classification matched, defaulting to accept"
        state.confidence = "medium"
        state.status = "accepted_with_disclaimer"

    latency_ms = int((time.time() - start) * 1000)

    state.log_node({
        "node": NODE_NAME,
        "timestamp": time.time(),
        "decision": decision,
        "reason": reason,
        "attempt_count": state.attempt_count,
        "hallucination_history_size": len(state.hallucination_history),
        "input_tokens": 0,
        "output_tokens": 0,
        "latency_ms": latency_ms,
        "cost_estimate": 0.0,
    })

    print(f"[TRACE]   ROUTER decision: {decision} — {reason}")
    logger.info(f"ROUTER decision: {decision} — {reason}")
    return decision
