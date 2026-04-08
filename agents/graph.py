"""
Agent Graph Orchestrator

Runs the ATS Resume Evaluator pipeline: a directed graph of nodes
with routing logic that handles verification loops, patching, and escalation.
"""

import logging
from typing import Optional, Callable

from agents.state import AgentState
from agents.nodes import (
    file_intake,
    jd_extraction,
    resume_evaluation,
    evidence_verification,
    severity_classification,
    router,
    patch_recalculate,
    re_evaluation,
    escalation,
    final_output,
)
from utils.observability import create_trace

logger = logging.getLogger(__name__)


def run_pipeline(
    state: AgentState,
    jd_requirements: Optional[dict] = None,
    on_node_complete: Optional[Callable] = None,
) -> AgentState:
    """
    Execute the full ATS evaluation pipeline for a single resume.

    Args:
        state: Pre-initialized AgentState with inputs set.
        jd_requirements: Pre-extracted JD requirements (skip JD extraction if provided).
        on_node_complete: Optional callback(node_name, state) for progress tracking.

    Returns:
        AgentState with final evaluation results.
    """
    trace = create_trace(state.trace_id, {"resume": state.resume_filename})

    def _notify(node_name: str):
        if on_node_complete:
            try:
                on_node_complete(node_name, state)
            except Exception as e:
                logger.warning(f"on_node_complete callback failed: {e}")

    print("\n" + "#" * 80)
    print(f"[TRACE] ### PIPELINE START for: {state.resume_filename}")
    print(f"[TRACE]   File path : {state.resume_file_path}")
    print(f"[TRACE]   File type : {state.resume_file_type}")
    print(f"[TRACE]   Model     : {state.current_model}")
    print("#" * 80)

    # --- Node 1: FILE_INTAKE ---
    print(f"\n[TRACE] >>> Node 1: FILE_INTAKE")
    span = trace.start_span("FILE_INTAKE")
    state = file_intake.run(state)
    trace.end_span(span, error=state.error)
    _notify("FILE_INTAKE")
    print(f"[TRACE] <<< Node 1: FILE_INTAKE — error={state.error}")

    if state.error:
        trace.end_trace()
        return state

    # --- Node 2: JD_EXTRACTION (skip if pre-extracted) ---
    if jd_requirements:
        print(f"\n[TRACE] >>> Node 2: JD_EXTRACTION (CACHED — skipping LLM call)")
        state.jd_requirements = jd_requirements
        state.path_taken.append("JD_EXTRACTION (cached)")
        _notify("JD_EXTRACTION")
    else:
        print(f"\n[TRACE] >>> Node 2: JD_EXTRACTION")
        span = trace.start_span("JD_EXTRACTION")
        state = jd_extraction.run(state)
        trace.end_span(span, error=state.error)
        _notify("JD_EXTRACTION")
        print(f"[TRACE] <<< Node 2: JD_EXTRACTION — error={state.error}")

        if state.error:
            trace.end_trace()
            return state

    # --- Node 3: RESUME_EVALUATION ---
    print(f"\n[TRACE] >>> Node 3: RESUME_EVALUATION (attempt #{state.attempt_count + 1})")
    span = trace.start_span("RESUME_EVALUATION")
    state = resume_evaluation.run(state)
    trace.end_span(span, error=state.error)
    _notify("RESUME_EVALUATION")
    print(f"[TRACE] <<< Node 3: RESUME_EVALUATION — score={state.overall_score}, error={state.error}")

    if state.error:
        trace.end_trace()
        return state

    # --- Verification Loop ---
    max_loops = 5  # safety limit to prevent infinite loops
    loop_count = 0

    print(f"\n[TRACE] >>> Entering verification loop (max {max_loops} iterations)")

    while loop_count < max_loops:
        loop_count += 1
        print(f"\n[TRACE] --- Verification loop iteration {loop_count}/{max_loops} ---")

        # --- Node 4: EVIDENCE_VERIFICATION ---
        print(f"[TRACE] >>> Node 4: EVIDENCE_VERIFICATION")
        span = trace.start_span("EVIDENCE_VERIFICATION")
        state = evidence_verification.run(state)
        trace.end_span(span, error=state.error)
        _notify("EVIDENCE_VERIFICATION")
        print(f"[TRACE] <<< Node 4: EVIDENCE_VERIFICATION — supported={len(state.supported_claims)}, unsupported={len(state.unsupported_claims)}, error={state.error}")

        if state.error:
            break

        # Check if all claims are supported
        if not state.unsupported_claims:
            print(f"[TRACE]   All claims SUPPORTED — exiting loop")
            state.confidence = state.confidence or "high"
            if not state.status:
                state.status = "accepted" if state.attempt_count <= 1 else "re-evaluated"
            break

        # --- Node 5: SEVERITY_CLASSIFICATION ---
        print(f"[TRACE] >>> Node 5: SEVERITY_CLASSIFICATION")
        span = trace.start_span("SEVERITY_CLASSIFICATION")
        state = severity_classification.run(state)
        trace.end_span(span, error=state.error)
        _notify("SEVERITY_CLASSIFICATION")
        print(f"[TRACE] <<< Node 5: SEVERITY_CLASSIFICATION — critical={state.has_critical}, moderate={state.has_moderate}, all_minor={state.all_minor}, error={state.error}")

        if state.error:
            break

        # --- Node 6: ROUTER ---
        print(f"[TRACE] >>> Node 6: ROUTER")
        span = trace.start_span("ROUTER")
        next_node = router.run(state)
        trace.end_span(span)
        _notify("ROUTER")
        print(f"[TRACE] <<< Node 6: ROUTER — decision={next_node}")

        # --- Execute routed node ---
        if next_node == "FINAL_OUTPUT":
            print(f"[TRACE]   Router says FINAL_OUTPUT — exiting loop")
            break

        elif next_node == "PATCH_AND_RECALCULATE":
            print(f"[TRACE] >>> Node 7: PATCH_AND_RECALCULATE (score before={state.overall_score})")
            span = trace.start_span("PATCH_AND_RECALCULATE")
            state = patch_recalculate.run(state)
            trace.end_span(span, error=state.error)
            _notify("PATCH_AND_RECALCULATE")
            print(f"[TRACE] <<< Node 7: PATCH_AND_RECALCULATE — score after={state.overall_score}, error={state.error}")
            if state.error:
                break
            print(f"[TRACE]   Looping back to EVIDENCE_VERIFICATION...")

        elif next_node == "FULL_RE_EVALUATION":
            print(f"[TRACE] >>> Node 8: FULL_RE_EVALUATION (attempt #{state.attempt_count}, hallucination_history={len(state.hallucination_history)} items)")
            span = trace.start_span("FULL_RE_EVALUATION")
            state = re_evaluation.run(state)
            trace.end_span(span, error=state.error)
            _notify("FULL_RE_EVALUATION")
            print(f"[TRACE] <<< Node 8: FULL_RE_EVALUATION — new score={state.overall_score}, error={state.error}")
            if state.error:
                break
            print(f"[TRACE]   Looping back to EVIDENCE_VERIFICATION...")

        elif next_node == "ESCALATION":
            print(f"[TRACE] >>> Node 9: ESCALATION (attempts exhausted={state.attempt_count})")
            span = trace.start_span("ESCALATION")
            esc_route = escalation.run(state)
            trace.end_span(span)
            _notify("ESCALATION")
            print(f"[TRACE] <<< Node 9: ESCALATION — sub-route={esc_route}")

            if esc_route == "RESUME_EVALUATION":
                # Model upgrade: re-enter evaluation
                print(f"[TRACE] >>> RESUME_EVALUATION (escalated, model={state.current_model})")
                span = trace.start_span("RESUME_EVALUATION (escalated)")
                state = resume_evaluation.run(state)
                trace.end_span(span, error=state.error)
                _notify("RESUME_EVALUATION")
                print(f"[TRACE] <<< RESUME_EVALUATION (escalated) — score={state.overall_score}, error={state.error}")
                if state.error:
                    break
                print(f"[TRACE]   Looping back to EVIDENCE_VERIFICATION...")
            else:
                # Deterministic or human review — go to final
                print(f"[TRACE]   Escalation resolved to FINAL_OUTPUT — exiting loop")
                break

        else:
            logger.error(f"Unknown route: {next_node}")
            state.error = f"Unknown routing decision: {next_node}"
            print(f"[TRACE]   !!! UNKNOWN ROUTE: {next_node}")
            break

    # --- Node 10: FINAL_OUTPUT ---
    print(f"\n[TRACE] >>> Node 10: FINAL_OUTPUT")
    span = trace.start_span("FINAL_OUTPUT")
    state = final_output.run(state)
    trace.end_span(span)
    _notify("FINAL_OUTPUT")

    print(f"[TRACE] <<< Node 10: FINAL_OUTPUT — final_score={state.final_score}, confidence={state.confidence}, status={state.status}")
    print(f"[TRACE]   Path taken: {' -> '.join(state.path_taken)}")
    print(f"[TRACE] ### PIPELINE END for: {state.resume_filename}")
    print("#" * 80 + "\n")

    trace.end_trace(state.final_evaluation)
    return state
