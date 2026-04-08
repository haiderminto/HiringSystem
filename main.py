"""
ATS Resume Evaluator — FastAPI Application

Endpoints:
  GET  /             → Serve the frontend
  GET  /api/health   → Health check
  POST /api/evaluate → Evaluate resumes against a job description (NDJSON streaming)
"""

import os
import sys
import json
import time
import asyncio
import logging
import traceback
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from agents.state import AgentState
from agents.graph import run_pipeline
from agents.nodes import jd_extraction
from utils.storage import get_upload_folder, save_uploaded_file, save_results, ensure_directories

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ats")

# Ensure directories exist
ensure_directories()

app = FastAPI(
    title="ATS Resume Evaluator",
    description="AI-powered resume evaluation agent with hallucination detection",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler to prevent worker crashes and return JSON errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/api/health")
async def health():
    """Health check — confirms server is running and config is valid."""
    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "model": settings.active_default_model,
        "api_key_set": bool(settings.active_api_key) and not settings.active_api_key.endswith("here"),
    }


@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.post("/api/evaluate")
async def evaluate_resumes(
    job_description: str = Form(...),
    resumes: List[UploadFile] = File(...),
):
    """
    Evaluate one or more resumes against a job description.
    Returns NDJSON streaming response with per-resume results.
    """
    print("\n" + "=" * 80)
    print("[TRACE] >>> API HIT: POST /api/evaluate")
    print(f"[TRACE]   JD length        : {len(job_description)} chars")
    print(f"[TRACE]   JD preview       : {job_description[:150]}...")
    print(f"[TRACE]   Resumes count    : {len(resumes)}")
    print(f"[TRACE]   Resume filenames : {[r.filename for r in resumes]}")
    print(f"[TRACE]   LLM provider     : {settings.llm_provider}")
    print(f"[TRACE]   Default model    : {settings.active_default_model}")
    print("=" * 80)

    if not settings.active_api_key or settings.active_api_key.endswith("here"):
        provider = settings.llm_provider.upper()
        raise HTTPException(
            status_code=500,
            detail=f"{provider} API key not configured. Update your .env file."
        )

    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description is required.")

    if not resumes:
        raise HTTPException(status_code=400, detail="At least one resume file is required.")

    # Validate file types
    allowed_extensions = {".pdf", ".docx"}
    for resume in resumes:
        ext = os.path.splitext(resume.filename or "")[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file: {resume.filename}. Only PDF and DOCX are accepted."
            )

    # Read file bytes upfront (before generator), since UploadFile may not be
    # readable after the endpoint returns the StreamingResponse.
    resume_data = []
    for resume in resumes:
        file_bytes = await resume.read()
        resume_data.append({"filename": resume.filename, "bytes": file_bytes})

    async def generate():
        results = []
        jd_requirements = None

        # Create upload folder inside the generator so it doesn't trigger
        # uvicorn's file-watcher reload before the response starts.
        upload_folder = get_upload_folder()

        # --- Step 1: Extract JD requirements (once) ---
        try:
            print("\n[TRACE] --- Step 1: Extracting JD requirements ---")
            yield _ndjson({"type": "status", "message": "Extracting job requirements..."})

            jd_state = AgentState(job_description_text=job_description)
            jd_state.current_model = settings.active_default_model
            jd_state = await asyncio.to_thread(jd_extraction.run, jd_state)

            if jd_state.error:
                yield _ndjson({"type": "error", "message": f"JD extraction failed: {jd_state.error}"})
                return

            jd_requirements = jd_state.jd_requirements

            print(f"[TRACE]   JD extraction complete: {len(jd_requirements.get('hard_skills', []))} hard skills, "
                  f"{len(jd_requirements.get('soft_skills', []))} soft skills, "
                  f"{len(jd_requirements.get('deal_breakers', []))} deal-breakers")

            yield _ndjson({
                "type": "jd_extracted",
                "data": jd_requirements,
                "message": f"Extracted {len(jd_requirements.get('hard_skills', []))} hard skills, "
                           f"{len(jd_requirements.get('soft_skills', []))} soft skills, "
                           f"{len(jd_requirements.get('deal_breakers', []))} deal-breakers"
            })

        except Exception as e:
            logger.error(f"JD extraction error: {e}")
            yield _ndjson({"type": "error", "message": f"JD extraction error: {str(e)}"})
            return

        # --- Step 2: Process each resume ---
        total = len(resume_data)
        for idx, rdata in enumerate(resume_data):
            filename = rdata["filename"] or f"resume_{idx}"
            ext = os.path.splitext(filename)[1].lower()
            file_type = "pdf" if ext == ".pdf" else "docx"

            print(f"\n[TRACE] --- Step 2: Processing resume {idx + 1}/{total} ---")
            print(f"[TRACE]   Filename  : {filename}")
            print(f"[TRACE]   File type : {file_type}")

            yield _ndjson({
                "type": "resume_started",
                "index": idx,
                "filename": filename,
                "total": total,
                "message": f"Processing {filename} ({idx + 1}/{total})..."
            })

            try:
                # Save uploaded file
                file_path = save_uploaded_file(rdata["bytes"], filename, upload_folder)

                # Initialize state for this resume
                state = AgentState(
                    job_description_text=job_description,
                    resume_file_path=file_path,
                    resume_file_type=file_type,
                    resume_filename=filename,
                    current_model=settings.active_default_model,
                )

                # Run the pipeline (blocking LLM calls run in thread)
                state = await asyncio.to_thread(
                    run_pipeline,
                    state,
                    jd_requirements,
                )

                if state.error:
                    print(f"[TRACE]   Pipeline ERROR for {filename}: {state.error}")
                    yield _ndjson({
                        "type": "resume_error",
                        "index": idx,
                        "filename": filename,
                        "message": f"Error processing {filename}: {state.error}"
                    })
                    continue

                result = state.final_evaluation
                results.append(result)
                print(f"[TRACE]   Pipeline COMPLETE for {filename} — score={result.get('candidate_evaluation', {}).get('overall_score', 'N/A')}")

                yield _ndjson({
                    "type": "resume_completed",
                    "index": idx,
                    "filename": filename,
                    "result": result,
                })

            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                yield _ndjson({
                    "type": "resume_error",
                    "index": idx,
                    "filename": filename,
                    "message": str(e)
                })

        # --- Step 3: Rank and return final results ---
        print(f"\n[TRACE] --- Step 3: Ranking {len(results)} results ---")
        ranked = sorted(results, key=lambda r: r.get("candidate_evaluation", {}).get("overall_score", 0), reverse=True)
        for rank_idx, r in enumerate(ranked):
            cand = r.get("candidate_evaluation", {})
            print(f"[TRACE]   Rank #{rank_idx + 1}: score={cand.get('overall_score', 'N/A')}, "
                  f"confidence={r.get('confidence', 'N/A')}, status={r.get('status', 'N/A')}")
        print("[TRACE] >>> API RESPONSE COMPLETE\n" + "=" * 80)

        # Save results to file
        try:
            save_results({"ranked_results": ranked, "jd_requirements": jd_requirements}, upload_folder)
        except Exception as e:
            logger.warning(f"Failed to save results file: {e}")

        yield _ndjson({
            "type": "all_complete",
            "total_processed": len(results),
            "results": ranked,
        })

    return StreamingResponse(generate(), media_type="application/x-ndjson")


# ── Local folder-based evaluate (bypasses proxy/file-upload issues) ────────
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@app.get("/api/evaluate-local")
async def evaluate_local(resume_folder: str, job_description: str = ""):
    """
    Evaluate resumes from a local folder path — GET request to bypass proxy.
    Query params: ?resume_folder=...&job_description=...
    If job_description is empty, falls back to JD_TEXT from .env.
    """
    job_description = job_description.strip() or settings.jd_text.strip()
    resume_folder = resume_folder.strip()

    print("\n" + "=" * 80)
    print("[TRACE] >>> API HIT: GET /api/evaluate-local")
    print(f"[TRACE]   JD length        : {len(job_description)} chars")
    print(f"[TRACE]   Resume folder    : {resume_folder}")
    print(f"[TRACE]   LLM provider     : {settings.llm_provider}")
    print(f"[TRACE]   Default model    : {settings.active_default_model}")
    print("=" * 80)

    if not settings.active_api_key or settings.active_api_key.endswith("here"):
        provider = settings.llm_provider.upper()
        raise HTTPException(status_code=500, detail=f"{provider} API key not configured.")

    if not job_description:
        raise HTTPException(status_code=400, detail="Job description is required.")

    if not resume_folder or not os.path.isdir(resume_folder):
        raise HTTPException(status_code=400, detail=f"Resume folder not found: {resume_folder}")

    # Discover resume files in folder
    resume_files = []
    for fname in sorted(os.listdir(resume_folder)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in ALLOWED_EXTENSIONS:
            resume_files.append(os.path.join(resume_folder, fname))

    if not resume_files:
        raise HTTPException(status_code=400, detail=f"No PDF/DOCX files found in {resume_folder}")

    async def generate():
        results = []
        jd_requirements = None

        # --- Step 1: Extract JD requirements ---
        try:
            yield _ndjson({"type": "status", "message": "Extracting job requirements..."})

            jd_state = AgentState(job_description_text=job_description)
            jd_state.current_model = settings.active_default_model
            jd_state = await asyncio.to_thread(jd_extraction.run, jd_state)

            if jd_state.error:
                yield _ndjson({"type": "error", "message": f"JD extraction failed: {jd_state.error}"})
                return

            jd_requirements = jd_state.jd_requirements
            yield _ndjson({
                "type": "jd_extracted",
                "data": jd_requirements,
                "message": f"Extracted {len(jd_requirements.get('hard_skills', []))} hard skills, "
                           f"{len(jd_requirements.get('soft_skills', []))} soft skills, "
                           f"{len(jd_requirements.get('deal_breakers', []))} deal-breakers"
            })
        except Exception as e:
            logger.error(f"JD extraction error: {e}")
            yield _ndjson({"type": "error", "message": f"JD extraction error: {str(e)}"})
            return

        # --- Step 2: Process each resume from the folder ---
        total = len(resume_files)
        for idx, file_path in enumerate(resume_files):
            filename = os.path.basename(file_path)
            ext = os.path.splitext(filename)[1].lower()
            file_type = "pdf" if ext == ".pdf" else "docx"

            yield _ndjson({
                "type": "resume_started",
                "index": idx,
                "filename": filename,
                "total": total,
                "message": f"Processing {filename} ({idx + 1}/{total})..."
            })

            try:
                state = AgentState(
                    job_description_text=job_description,
                    resume_file_path=file_path,
                    resume_file_type=file_type,
                    resume_filename=filename,
                    current_model=settings.active_default_model,
                )

                state = await asyncio.to_thread(run_pipeline, state, jd_requirements)

                if state.error:
                    yield _ndjson({"type": "resume_error", "index": idx, "filename": filename, "message": state.error})
                    continue

                result = state.final_evaluation
                results.append(result)
                yield _ndjson({"type": "resume_completed", "index": idx, "filename": filename, "result": result})

            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                yield _ndjson({"type": "resume_error", "index": idx, "filename": filename, "message": str(e)})

        # --- Step 3: Rank results ---
        ranked = sorted(results, key=lambda r: r.get("candidate_evaluation", {}).get("overall_score", 0), reverse=True)

        try:
            ensure_directories()
            results_path = os.path.join(settings.results_dir, "evaluation_results.json")
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump({"ranked_results": ranked, "jd_requirements": jd_requirements}, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save results: {e}")

        yield _ndjson({"type": "all_complete", "total_processed": len(results), "results": ranked})

    return StreamingResponse(generate(), media_type="application/x-ndjson")


def _ndjson(obj: dict) -> str:
    """Serialize an object as a single NDJSON line."""
    return json.dumps(obj, default=str) + "\n"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[os.path.dirname(__file__) or "."],
        reload_includes=["*.py"],
    )
