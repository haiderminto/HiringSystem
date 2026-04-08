import json
import time
import logging

from agents.state import AgentState
from agents.prompts.jd_extraction import JD_EXTRACTION_PROMPT, JD_EXTRACTION_SYSTEM
from utils.llm_client import call_llm_json

logger = logging.getLogger(__name__)

NODE_NAME = "JD_EXTRACTION"

REQUIRED_KEYS = ["job_title", "hard_skills", "deal_breakers"]


def _validate_jd_json(data: dict) -> bool:
    """Check that the extracted JD JSON has required structure."""
    for key in REQUIRED_KEYS:
        if key not in data:
            return False

    # hard_skills must be a non-empty list with proper structure
    if not isinstance(data.get("hard_skills"), list) or len(data["hard_skills"]) == 0:
        return False

    for skill in data["hard_skills"]:
        if not isinstance(skill, dict) or "skill" not in skill or "priority" not in skill:
            return False

    # deal_breakers must be a list (can be empty)
    if not isinstance(data.get("deal_breakers"), list):
        return False

    return True


def run(state: AgentState) -> AgentState:
    """
    Node 2: Extract structured requirements from the job description.
    """
    start = time.time()
    state.current_node = NODE_NAME
    state.path_taken.append(NODE_NAME)

    prompt = JD_EXTRACTION_PROMPT.format(job_description=state.job_description_text)

    print(f"[TRACE]   JD_EXTRACTION: model={state.current_model}, prompt_len={len(prompt)} chars")
    print(f"[TRACE]   JD text preview: {state.job_description_text[:150]}...")

    try:
        result = call_llm_json(
            prompt=prompt,
            model=state.current_model,
            system_prompt=JD_EXTRACTION_SYSTEM,
        )

        parsed = result.get("parsed")
        parse_attempts = 1

        if parsed is None:
            state.error = "Could not parse job description into structured format after 2 attempts."
            state.log_node({
                "node": NODE_NAME,
                "timestamp": time.time(),
                "model": state.current_model,
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "parse_attempts": 2,
                "parse_success": False,
                "latency_ms": result.get("latency_ms", 0),
                "cost_estimate": result.get("cost_estimate", 0),
            })
            return state

        # Validate structure
        if not _validate_jd_json(parsed):
            # One more attempt with explicit schema
            logger.warning("JD JSON validation failed, retrying with schema enforcement")
            from utils.llm_client import call_llm_json as retry_call
            retry_result = retry_call(
                prompt=prompt + "\n\nENSURE the output contains these required keys: job_title, hard_skills (non-empty list of {{skill, priority}} objects), deal_breakers (list). Do NOT omit any key.",
                model=state.current_model,
                system_prompt=JD_EXTRACTION_SYSTEM,
                retry_on_parse_fail=False,
            )
            parse_attempts = 2
            retry_parsed = retry_result.get("parsed")
            if retry_parsed and _validate_jd_json(retry_parsed):
                parsed = retry_parsed
                result["input_tokens"] += retry_result.get("input_tokens", 0)
                result["output_tokens"] += retry_result.get("output_tokens", 0)
                result["cost_estimate"] += retry_result.get("cost_estimate", 0)
                result["latency_ms"] += retry_result.get("latency_ms", 0)
            else:
                state.error = "JD extraction produced invalid structure after retries."
                return state

        state.jd_requirements = parsed

        hard_skills_count = len(parsed.get("hard_skills", []))
        soft_skills_count = len(parsed.get("soft_skills", []))
        deal_breakers_count = len(parsed.get("deal_breakers", []))

        print(f"[TRACE]   JD_EXTRACTION result: job_title='{parsed.get('job_title', 'N/A')}', "
              f"hard_skills={hard_skills_count}, soft_skills={soft_skills_count}, deal_breakers={deal_breakers_count}")
        print(f"[TRACE]   Hard skills: {[s.get('skill', '') for s in parsed.get('hard_skills', [])[:5]]}{'...' if hard_skills_count > 5 else ''}")
        print(f"[TRACE]   Deal breakers: {parsed.get('deal_breakers', [])}")

        latency_ms = int((time.time() - start) * 1000)

        state.log_node({
            "node": NODE_NAME,
            "timestamp": time.time(),
            "model": state.current_model,
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "parse_attempts": parse_attempts,
            "parse_success": True,
            "extracted_hard_skills_count": hard_skills_count,
            "extracted_soft_skills_count": soft_skills_count,
            "deal_breakers_count": deal_breakers_count,
            "latency_ms": latency_ms,
            "cost_estimate": result.get("cost_estimate", 0),
        })

    except Exception as e:
        logger.error(f"JD_EXTRACTION error: {e}")
        state.error = f"JD extraction failed: {str(e)}"

    return state
