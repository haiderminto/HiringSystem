import json
import time
import logging

from agents.state import AgentState
from agents.prompts.evidence_verification import (
    EVIDENCE_VERIFICATION_PROMPT,
    EVIDENCE_VERIFICATION_SYSTEM,
)
from utils.llm_client import call_llm_json

logger = logging.getLogger(__name__)

NODE_NAME = "EVIDENCE_VERIFICATION"


def run(state: AgentState) -> AgentState:
    """
    Node 4: Verify every claim in the evaluation against the actual resume.
    """
    start = time.time()
    state.current_node = NODE_NAME
    state.path_taken.append(NODE_NAME)

    print(f"[TRACE]   EVIDENCE_VERIFICATION: model={state.current_model}, "
          f"matched_reqs_to_verify={len(state.matched_requirements)}")

    # Build evaluation summary for verification
    eval_summary = json.dumps({
        "matched_requirements": state.matched_requirements,
        "summary": state.evaluation.get("summary", "") if state.evaluation else "",
        "overall_score": state.overall_score,
        "category_scores": state.category_scores,
    }, indent=2)

    resume_content = state.resume_extracted_text or "(Resume content sent as PDF document)"

    prompt = EVIDENCE_VERIFICATION_PROMPT.format(
        evaluation=eval_summary,
        resume_text=resume_content,
    )

    pdf_base64 = state.resume_base64
    resume_markdown = state.resume_markdown

    try:
        result = call_llm_json(
            prompt=prompt,
            model=state.current_model,
            pdf_base64=pdf_base64,
            resume_markdown=resume_markdown,
            system_prompt=EVIDENCE_VERIFICATION_SYSTEM,
            max_tokens=4096,
        )

        parsed = result.get("parsed")
        if parsed is None:
            # If verification parsing fails, accept the evaluation with medium confidence
            logger.warning("Verification parse failed, accepting evaluation with medium confidence")
            state.confidence = "medium"
            state.status = "accepted_verification_skipped"
            state.verification_report = []
            state.supported_claims = state.matched_requirements
            state.unsupported_claims = []
        else:
            # Ensure parsed is a list
            if isinstance(parsed, dict) and "claims" in parsed:
                claims = parsed["claims"]
            elif isinstance(parsed, list):
                claims = parsed
            else:
                claims = []

            state.verification_report = claims

            state.supported_claims = [
                c for c in claims if c.get("status") == "SUPPORTED"
            ]
            state.unsupported_claims = [
                c for c in claims if c.get("status") == "UNSUPPORTED"
            ]

        total_claims = len(state.supported_claims) + len(state.unsupported_claims)
        verification_rate = len(state.supported_claims) / max(total_claims, 1)

        print(f"[TRACE]   EVIDENCE_VERIFICATION result: total_claims={total_claims}, "
              f"supported={len(state.supported_claims)}, unsupported={len(state.unsupported_claims)}, "
              f"verification_rate={verification_rate:.1%}")
        if state.unsupported_claims:
            print(f"[TRACE]   Unsupported claims: {[c.get('claim', '')[:60] for c in state.unsupported_claims]}")

        latency_ms = int((time.time() - start) * 1000)

        state.log_node({
            "node": NODE_NAME,
            "timestamp": time.time(),
            "model": state.current_model,
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "total_claims_checked": total_claims,
            "supported_count": len(state.supported_claims),
            "unsupported_count": len(state.unsupported_claims),
            "verification_rate": round(verification_rate, 3),
            "latency_ms": latency_ms,
            "cost_estimate": result.get("cost_estimate", 0),
        })

    except Exception as e:
        logger.error(f"EVIDENCE_VERIFICATION error: {e}")
        state.error = f"Evidence verification failed: {str(e)}"

    return state
