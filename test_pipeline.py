"""
Test the ATS pipeline directly — no HTTP server, no proxy, no UI.

Reads JD_TEXT and RESUME_FOLDER from .env, processes all PDF/DOCX files
in that folder, and prints results to the console.

Usage:
  1. Put your resume PDF/DOCX files in the 'resumes/' folder
  2. Edit JD_TEXT in .env (or leave the default)
  3. Run: python test_pipeline.py
"""

import os
import sys
import json
import time
import shutil

from dotenv import load_dotenv
load_dotenv()

from config import settings
from agents.state import AgentState
from agents.graph import run_pipeline
from agents.nodes import jd_extraction
from utils.storage import ensure_directories

# ── Configuration ──────────────────────────────────────────────────────────
RESUME_FOLDER = os.getenv("RESUME_FOLDER", "resumes")
JD_TEXT = os.getenv("JD_TEXT", "")

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def find_resumes(folder: str) -> list:
    """Find all PDF/DOCX files in the given folder."""
    if not os.path.isdir(folder):
        return []
    files = []
    for fname in sorted(os.listdir(folder)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in ALLOWED_EXTENSIONS:
            files.append(os.path.join(folder, fname))
    return files


def main():
    print("=" * 70)
    print("  ATS Pipeline — Direct Test (no HTTP / no proxy)")
    print("=" * 70)

    # ── Validate config ────────────────────────────────────────────────
    print(f"\nProvider        : {settings.llm_provider}")
    print(f"Model           : {settings.active_default_model}")
    print(f"API key set     : {bool(settings.active_api_key) and not settings.active_api_key.endswith('here')}")
    print(f"Resume folder   : {os.path.abspath(RESUME_FOLDER)}")
    print(f"JD length       : {len(JD_TEXT)} chars")

    if not settings.active_api_key or settings.active_api_key.endswith("here"):
        print(f"\nERROR: {settings.llm_provider.upper()} API key not configured in .env")
        sys.exit(1)

    if not JD_TEXT.strip():
        print("\nERROR: JD_TEXT is empty in .env")
        sys.exit(1)

    resumes = find_resumes(RESUME_FOLDER)
    if not resumes:
        print(f"\nERROR: No PDF/DOCX files found in '{os.path.abspath(RESUME_FOLDER)}'")
        print("       Place your resume files there and re-run.")
        sys.exit(1)

    print(f"Resumes found   : {len(resumes)}")
    for r in resumes:
        print(f"  - {os.path.basename(r)}")

    ensure_directories()

    # ── Step 1: Extract JD requirements ────────────────────────────────
    print(f"\n{'─' * 70}")
    print("Step 1: Extracting job description requirements...")
    print(f"{'─' * 70}")

    jd_state = AgentState(job_description_text=JD_TEXT)
    jd_state.current_model = settings.active_default_model

    try:
        jd_state = jd_extraction.run(jd_state)
    except Exception as e:
        print(f"\nFATAL: JD extraction crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if jd_state.error:
        print(f"\nERROR: JD extraction failed: {jd_state.error}")
        sys.exit(1)

    jd_req = jd_state.jd_requirements
    print(f"\nExtracted:")
    print(f"  Job title     : {jd_req.get('job_title', 'N/A')}")
    print(f"  Hard skills   : {len(jd_req.get('hard_skills', []))}")
    print(f"  Soft skills   : {len(jd_req.get('soft_skills', []))}")
    print(f"  Deal-breakers : {len(jd_req.get('deal_breakers', []))}")

    # ── Step 2: Evaluate each resume ──────────────────────────────────
    results = []

    for idx, resume_path in enumerate(resumes):
        filename = os.path.basename(resume_path)
        ext = os.path.splitext(filename)[1].lower()
        file_type = "pdf" if ext == ".pdf" else "docx"

        print(f"\n{'─' * 70}")
        print(f"Step 2: Processing resume {idx + 1}/{len(resumes)} — {filename}")
        print(f"{'─' * 70}")

        state = AgentState(
            job_description_text=JD_TEXT,
            resume_file_path=resume_path,
            resume_file_type=file_type,
            resume_filename=filename,
            current_model=settings.active_default_model,
        )

        try:
            t0 = time.time()
            state = run_pipeline(state, jd_req)
            elapsed = time.time() - t0
        except Exception as e:
            print(f"\nFATAL: Pipeline crashed for {filename}: {e}")
            import traceback
            traceback.print_exc()
            continue

        if state.error:
            print(f"\nERROR: Pipeline error for {filename}: {state.error}")
            continue

        result = state.final_evaluation
        results.append(result)

        cand = result.get("candidate_evaluation", {})
        meta = result.get("reliability_metadata", {})
        audit = result.get("audit_trail", {})

        print(f"\n  Score          : {cand.get('overall_score', 'N/A')}/10")
        print(f"  Deal-breaker   : {cand.get('deal_breaker_check', {}).get('status', 'N/A')}")
        print(f"  Confidence     : {meta.get('confidence', 'N/A')}")
        print(f"  Status         : {meta.get('status', 'N/A')}")
        print(f"  Verification   : {meta.get('verification_rate', 0):.0%}")
        print(f"  Hallucinations : {meta.get('hallucinations_caught', 0)}")
        print(f"  Tokens         : {audit.get('total_tokens', {}).get('total', 0)}")
        print(f"  Cost           : ${audit.get('total_cost_estimate', 0):.4f}")
        print(f"  Latency        : {elapsed:.1f}s")

        # Category scores
        cats = cand.get("category_scores", {})
        if cats:
            print(f"  Category scores:")
            for k, v in cats.items():
                print(f"    {k:30s}: {v}/10")

    # ── Step 3: Final ranking ─────────────────────────────────────────
    if results:
        print(f"\n{'=' * 70}")
        print("  FINAL RANKING")
        print(f"{'=' * 70}")

        ranked = sorted(
            results,
            key=lambda r: r.get("candidate_evaluation", {}).get("overall_score", 0),
            reverse=True,
        )
        for rank, r in enumerate(ranked, 1):
            cand = r.get("candidate_evaluation", {})
            meta = r.get("reliability_metadata", {})
            print(f"  #{rank}  {r.get('resume_filename', '?'):30s}  "
                  f"Score: {cand.get('overall_score', 0):4.1f}/10  "
                  f"Confidence: {meta.get('confidence', '?')}")

        # Save results
        results_path = os.path.join(settings.results_dir, "test_results.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump({"ranked_results": ranked, "jd_requirements": jd_req}, f, indent=2, default=str)
        print(f"\nResults saved to: {os.path.abspath(results_path)}")
    else:
        print("\nNo results produced.")

    print(f"\n{'=' * 70}")
    print("  Done.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
