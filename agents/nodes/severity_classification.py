import json
import time
import logging

from agents.state import AgentState
from agents.prompts.severity_classification import (
    SEVERITY_CLASSIFICATION_PROMPT,
    SEVERITY_CLASSIFICATION_SYSTEM,
)
from utils.llm_client import call_llm_json

logger = logging.getLogger(__name__)

NODE_NAME = "SEVERITY_CLASSIFICATION"


def run(state: AgentState) -> AgentState:
    """
    Node 5: Classify each unsupported claim by severity.
    """
    start = time.time()
    state.current_node = NODE_NAME
    state.path_taken.append(NODE_NAME)

    print(f"[TRACE]   SEVERITY_CLASSIFICATION: model={state.current_model}, "
          f"unsupported_claims_count={len(state.unsupported_claims)}")

    unsupported_text = json.dumps(state.unsupported_claims, indent=2)
    eval_text = json.dumps(state.evaluation, indent=2)
    jd_text = json.dumps(state.jd_requirements, indent=2)

    prompt = SEVERITY_CLASSIFICATION_PROMPT.format(
        unsupported_claims=unsupported_text,
        evaluation=eval_text,
        jd_requirements=jd_text,
    )

    try:
        result = call_llm_json(
            prompt=prompt,
            model=state.current_model,
            system_prompt=SEVERITY_CLASSIFICATION_SYSTEM,
            max_tokens=2048,
        )

        parsed = result.get("parsed")
        if parsed is None:
            # If classification fails, treat all as moderate
            logger.warning("Severity classification parse failed, treating all as MODERATE")
            state.severity_report = [
                {"claim": c.get("claim", ""), "severity": "MODERATE", "reasoning": "Classification failed"}
                for c in state.unsupported_claims
            ]
        else:
            if isinstance(parsed, list):
                state.severity_report = parsed
            elif isinstance(parsed, dict) and "claims" in parsed:
                state.severity_report = parsed["claims"]
            else:
                state.severity_report = []

        # Compute flags
        severities = [item.get("severity", "MINOR") for item in state.severity_report]
        state.has_critical = "CRITICAL" in severities
        state.has_moderate = "MODERATE" in severities
        state.all_minor = all(s == "MINOR" for s in severities) if severities else True

        critical_count = severities.count("CRITICAL")
        moderate_count = severities.count("MODERATE")
        minor_count = severities.count("MINOR")

        print(f"[TRACE]   SEVERITY_CLASSIFICATION result: CRITICAL={critical_count}, "
              f"MODERATE={moderate_count}, MINOR={minor_count}")
        for item in state.severity_report:
            print(f"[TRACE]     - [{item.get('severity', '?')}] {item.get('claim', '')[:80]}")

        latency_ms = int((time.time() - start) * 1000)

        state.log_node({
            "node": NODE_NAME,
            "timestamp": time.time(),
            "model": state.current_model,
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "critical_count": critical_count,
            "moderate_count": moderate_count,
            "minor_count": minor_count,
            "latency_ms": latency_ms,
            "cost_estimate": result.get("cost_estimate", 0),
        })

    except Exception as e:
        logger.error(f"SEVERITY_CLASSIFICATION error: {e}")
        state.error = f"Severity classification failed: {str(e)}"

    return state
