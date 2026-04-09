import json
import time
import logging

from agents.state import AgentState
from agents.prompts.resume_evaluation import (
    RESUME_EVALUATION_PROMPT,
    RESUME_EVALUATION_SYSTEM,
    RESUME_EVALUATION_HALLUCINATION_CONSTRAINT,
)
from utils.llm_client import call_llm_json

logger = logging.getLogger(__name__)

NODE_NAME = "RESUME_EVALUATION"


def run(state: AgentState) -> AgentState:
    """
    Node 3: Score the resume against extracted JD requirements.
    """
    start = time.time()
    state.current_node = NODE_NAME
    state.path_taken.append(NODE_NAME)

    print(f"[TRACE]   RESUME_EVALUATION: model={state.current_model}, attempt_count={state.attempt_count}")
    print(f"[TRACE]   Has base64 PDF: {bool(state.resume_base64)}, Has markdown: {bool(state.resume_markdown)}, Has text: {bool(state.resume_extracted_text)}")
    print(f"[TRACE]   Hallucination history: {len(state.hallucination_history)} items")

    # Build the prompt
    jd_text = json.dumps(state.jd_requirements, indent=2)

    # Determine resume content for prompt
    resume_content = state.resume_extracted_text or "(Resume content sent as PDF document)"

    prompt = RESUME_EVALUATION_PROMPT.format(
        jd_requirements=jd_text,
        resume_text=resume_content,
    )

    # Add hallucination constraints if we have history
    hallucination_constraints_injected = False
    if state.hallucination_history:
        constraint = RESUME_EVALUATION_HALLUCINATION_CONSTRAINT.format(
            hallucination_history=json.dumps(state.hallucination_history, indent=2)
        )
        prompt = constraint + "\n\n" + prompt
        hallucination_constraints_injected = True

    # Send resume content in the appropriate format for the configured provider
    pdf_base64 = state.resume_base64
    resume_markdown = state.resume_markdown

    try:
        result = call_llm_json(
            prompt=prompt,
            model=state.current_model,
            pdf_base64=pdf_base64,
            resume_markdown=resume_markdown,
            system_prompt=RESUME_EVALUATION_SYSTEM,
            max_tokens=4096,
        )

        parsed = result.get("parsed")
        if parsed is None:
            state.error = "Could not parse resume evaluation response."
            return state

        # Extract fields from parsed evaluation
        state.evaluation = parsed
        state.overall_score = parsed.get("overall_score", 0)
        state.category_scores = parsed.get("category_scores", {})
        state.matched_requirements = parsed.get("matched_requirements", [])
        state.gaps = parsed.get("gaps", [])

        deal_breaker = parsed.get("deal_breaker_check", {})
        state.deal_breaker_status = deal_breaker.get("status", "PASS")

        # Extract candidate profile fields from LLM response
        profile = parsed.get("candidate_profile", {})
        if profile:
            state.candidate_total_experience = profile.get("total_experience_years", "")
            state.candidate_company = profile.get("current_company", "")
            state.candidate_location = profile.get("candidate_location", "")
            state.candidate_skill = profile.get("primary_skills", "")

        state.attempt_count += 1

        print(f"[TRACE]   RESUME_EVALUATION result: overall_score={state.overall_score}, "
              f"deal_breaker={state.deal_breaker_status}, "
              f"matched_reqs={len(state.matched_requirements)}, gaps={len(state.gaps)}, "
              f"attempt_count={state.attempt_count}")

        latency_ms = int((time.time() - start) * 1000)

        state.log_node({
            "node": NODE_NAME,
            "timestamp": time.time(),
            "model": state.current_model,
            "attempt_number": state.attempt_count,
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "resume_sent_as": "pdf_document_block" if pdf_base64 else ("markdown" if resume_markdown else "extracted_text"),
            "hallucination_constraints_injected": hallucination_constraints_injected,
            "overall_score": state.overall_score,
            "deal_breaker_status": state.deal_breaker_status,
            "latency_ms": latency_ms,
            "cost_estimate": result.get("cost_estimate", 0),
        })

    except Exception as e:
        logger.error(f"RESUME_EVALUATION error: {e}")
        state.error = f"Resume evaluation failed: {str(e)}"

    return state
