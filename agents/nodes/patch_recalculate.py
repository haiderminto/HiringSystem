import json
import time
import logging

from agents.state import AgentState
from agents.prompts.patch_recalculate import (
    PATCH_RECALCULATE_PROMPT,
    PATCH_RECALCULATE_SYSTEM,
)
from utils.llm_client import call_llm_json

logger = logging.getLogger(__name__)

NODE_NAME = "PATCH_AND_RECALCULATE"


def run(state: AgentState) -> AgentState:
    """
    Node 7: Correct the evaluation by removing unsupported claims and recalculating.
    """
    start = time.time()
    state.current_node = NODE_NAME
    state.path_taken.append(NODE_NAME)

    print(f"[TRACE]   PATCH_AND_RECALCULATE: model={state.current_model}, "
          f"score_before={state.overall_score}, unsupported_claims={len(state.unsupported_claims)}")

    # Format unsupported claims with severity
    unsupported_with_severity = []
    severity_map = {item.get("claim", ""): item for item in state.severity_report}

    for claim in state.unsupported_claims:
        claim_text = claim.get("claim", str(claim))
        severity_info = severity_map.get(claim_text, {})
        unsupported_with_severity.append({
            "claim": claim_text,
            "severity": severity_info.get("severity", "MODERATE"),
            "reasoning": severity_info.get("reasoning", ""),
            "estimated_score_impact": severity_info.get("estimated_score_impact", 1.0),
        })

    prompt = PATCH_RECALCULATE_PROMPT.format(
        unsupported_claims=json.dumps(unsupported_with_severity, indent=2),
        evaluation=json.dumps(state.evaluation, indent=2),
        supported_claims=json.dumps(state.supported_claims, indent=2),
        jd_requirements=json.dumps(state.jd_requirements, indent=2),
    )

    score_before = state.overall_score

    try:
        result = call_llm_json(
            prompt=prompt,
            model=state.current_model,
            system_prompt=PATCH_RECALCULATE_SYSTEM,
            max_tokens=4096,
        )

        parsed = result.get("parsed")
        if parsed is None:
            state.error = "Could not parse patched evaluation."
            return state

        # Overwrite evaluation with corrected version
        state.evaluation = parsed
        state.overall_score = parsed.get("overall_score", state.overall_score)
        state.category_scores = parsed.get("category_scores", state.category_scores)
        state.matched_requirements = parsed.get("matched_requirements", state.matched_requirements)
        state.gaps = parsed.get("gaps", state.gaps)

        deal_breaker = parsed.get("deal_breaker_check", {})
        state.deal_breaker_status = deal_breaker.get("status", state.deal_breaker_status)

        # Log what changed
        corrections = parsed.get("corrections_applied", [])
        claims_removed = len(corrections)

        state.patch_log.append({
            "method": "patch_and_recalculate",
            "score_before": score_before,
            "score_after": state.overall_score,
            "claims_removed": claims_removed,
            "corrections": corrections,
            "deal_breaker_changed": deal_breaker.get("status") != "PASS",
        })

        print(f"[TRACE]   PATCH_AND_RECALCULATE result: score {score_before} -> {state.overall_score}, "
              f"claims_removed={claims_removed}, deal_breaker_changed={deal_breaker.get('status') != 'PASS'}")

        latency_ms = int((time.time() - start) * 1000)

        state.log_node({
            "node": NODE_NAME,
            "timestamp": time.time(),
            "model": state.current_model,
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "claims_removed": claims_removed,
            "score_before": score_before,
            "score_after": state.overall_score,
            "deal_breaker_changed": deal_breaker.get("status") != "PASS",
            "latency_ms": latency_ms,
            "cost_estimate": result.get("cost_estimate", 0),
        })

    except Exception as e:
        logger.error(f"PATCH_AND_RECALCULATE error: {e}")
        state.error = f"Patch and recalculate failed: {str(e)}"

    return state
