import time
import logging

from agents.state import AgentState
from config import settings

logger = logging.getLogger(__name__)

NODE_NAME = "ESCALATION"

# Return values
ROUTE_RE_EVALUATE = "RESUME_EVALUATION"
ROUTE_FINAL = "FINAL_OUTPUT"


def _deterministic_score(state: AgentState) -> float:
    """
    Fallback deterministic scoring: keyword/skill matching without LLM.
    Searches resume text for each required skill.
    """
    if not state.jd_requirements or not state.resume_extracted_text:
        return 0.0

    resume_lower = state.resume_extracted_text.lower()
    hard_skills = state.jd_requirements.get("hard_skills", [])

    required_skills = [s for s in hard_skills if s.get("priority") == "required"]
    if not required_skills:
        required_skills = hard_skills  # treat all as required if none marked

    if not required_skills:
        return 5.0  # no skills to match against

    matched = 0
    matched_list = []
    gaps_list = []

    for skill_obj in required_skills:
        skill_name = skill_obj.get("skill", "").lower()
        # Check for exact or partial match
        if skill_name in resume_lower:
            matched += 1
            matched_list.append({
                "requirement": skill_obj.get("skill", ""),
                "evidence": f"Keyword '{skill_obj['skill']}' found in resume text"
            })
        else:
            # Try individual words for multi-word skills
            words = skill_name.split()
            if len(words) > 1 and all(w in resume_lower for w in words):
                matched += 1
                matched_list.append({
                    "requirement": skill_obj.get("skill", ""),
                    "evidence": f"All keywords for '{skill_obj['skill']}' found in resume text"
                })
            else:
                gaps_list.append({
                    "requirement": skill_obj.get("skill", ""),
                    "priority": skill_obj.get("priority", "required"),
                    "impact": "Not found in resume via keyword search"
                })

    score = round((matched / len(required_skills)) * 10, 1)
    score = max(1.0, min(10.0, score))

    # Update state with deterministic results
    state.matched_requirements = matched_list
    state.gaps = gaps_list
    state.overall_score = score
    state.category_scores = {
        "hard_skills_match": score,
        "soft_skills_match": 5.0,
        "experience_relevance": 5.0,
        "education_certifications": 5.0,
        "achievement_quality": 5.0,
    }

    return score


def run(state: AgentState) -> str:
    """
    Node 9: Handle cases where hallucinations persist after max attempts.

    Returns the next node to route to.
    """
    start = time.time()
    state.current_node = NODE_NAME
    state.path_taken.append(NODE_NAME)

    strategy_used = ""

    print(f"[TRACE]   ESCALATION: current_model={state.current_model}, "
          f"attempt_count={state.attempt_count}, "
          f"enable_model_escalation={settings.enable_model_escalation}, "
          f"escalation_model={settings.active_escalation_model}")
    print(f"[TRACE]   Hallucinations that persisted: {state.hallucination_history}")

    # Strategy A: Try stronger model (if enabled and not already using it)
    if (settings.enable_model_escalation and
            state.current_model != settings.active_escalation_model):
        strategy_used = "model_upgrade"
        state.current_model = settings.active_escalation_model
        state.attempt_count = 0  # Reset for the stronger model
        print(f"[TRACE]   ESCALATION strategy: MODEL UPGRADE -> {settings.active_escalation_model}")
        logger.info(f"ESCALATION: Upgrading model to {settings.active_escalation_model}")

        state.log_node({
            "node": NODE_NAME,
            "timestamp": time.time(),
            "strategy_used": strategy_used,
            "previous_model": settings.active_default_model,
            "new_model": settings.active_escalation_model,
            "previous_attempts": state.attempt_count,
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": int((time.time() - start) * 1000),
            "cost_estimate": 0.0,
        })
        return ROUTE_RE_EVALUATE

    # Strategy B: Deterministic scoring (no LLM)
    if state.resume_extracted_text:
        strategy_used = "deterministic_scoring"
        score = _deterministic_score(state)
        state.confidence = "low"
        state.status = "escalated_deterministic"
        state.final_score = score
        print(f"[TRACE]   ESCALATION strategy: DETERMINISTIC SCORING -> score={score}")
        logger.info(f"ESCALATION: Deterministic scoring produced score={score}")

        state.log_node({
            "node": NODE_NAME,
            "timestamp": time.time(),
            "strategy_used": strategy_used,
            "deterministic_score": score,
            "confidence": "low",
            "hallucinations_that_persisted": state.hallucination_history,
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": int((time.time() - start) * 1000),
            "cost_estimate": 0.0,
        })
        return ROUTE_FINAL

    # Strategy C: Human review flag
    strategy_used = "human_review"
    state.confidence = "none"
    state.status = "human_review_required"
    state.final_score = 0.0
    print(f"[TRACE]   ESCALATION strategy: HUMAN REVIEW (no text extraction available)")
    logger.info("ESCALATION: Flagged for human review")

    state.log_node({
        "node": NODE_NAME,
        "timestamp": time.time(),
        "strategy_used": strategy_used,
        "confidence": "none",
        "reason": "Resume text extraction was poor or unavailable",
        "input_tokens": 0,
        "output_tokens": 0,
        "latency_ms": int((time.time() - start) * 1000),
        "cost_estimate": 0.0,
    })
    return ROUTE_FINAL
