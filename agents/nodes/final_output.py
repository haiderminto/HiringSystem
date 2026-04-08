import time
import logging

from agents.state import AgentState

logger = logging.getLogger(__name__)

NODE_NAME = "FINAL_OUTPUT"


def run(state: AgentState) -> AgentState:
    """
    Node 10: Package the final result with all metadata, confidence, and audit trail.
    """
    start = time.time()
    state.current_node = NODE_NAME
    state.path_taken.append(NODE_NAME)

    print(f"[TRACE]   FINAL_OUTPUT: assembling result for {state.resume_filename}")

    # Set final score if not already set (by escalation/patching)
    if state.final_score == 0.0:
        state.final_score = state.overall_score

    # Set confidence if not already set
    if not state.confidence:
        if not state.unsupported_claims:
            state.confidence = "high"
        elif state.all_minor:
            state.confidence = "medium"
        else:
            state.confidence = "medium"

    # Set status if not already set
    if not state.status:
        if state.attempt_count <= 1 and not state.unsupported_claims:
            state.status = "accepted"
        elif state.patch_log:
            state.status = "patched"
        elif state.attempt_count > 1:
            state.status = "re-evaluated"
        else:
            state.status = "accepted"

    state.total_attempts = state.attempt_count

    # Build verification summary
    total_claims = len(state.supported_claims) + len(state.unsupported_claims)
    if total_claims > 0:
        rate = len(state.supported_claims) / total_claims
        state.verification_summary = (
            f"{len(state.supported_claims)}/{total_claims} claims verified "
            f"({rate:.0%} verification rate). "
            f"Confidence: {state.confidence}."
        )
    else:
        state.verification_summary = "No verification performed."

    # Package the final evaluation
    state.final_evaluation = state.to_final_output()

    latency_ms = int((time.time() - start) * 1000)

    state.log_node({
        "node": NODE_NAME,
        "timestamp": time.time(),
        "final_score": state.final_score,
        "confidence": state.confidence,
        "status": state.status,
        "total_attempts": state.total_attempts,
        "input_tokens": 0,
        "output_tokens": 0,
        "latency_ms": latency_ms,
        "cost_estimate": 0.0,
    })

    print(f"[TRACE]   FINAL_OUTPUT result: score={state.final_score}, confidence={state.confidence}, "
          f"status={state.status}, total_attempts={state.total_attempts}")
    print(f"[TRACE]   Verification: {state.verification_summary}")

    logger.info(
        f"FINAL_OUTPUT: score={state.final_score}, "
        f"confidence={state.confidence}, status={state.status}"
    )

    return state
