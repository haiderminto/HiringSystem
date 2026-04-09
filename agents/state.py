import re
import uuid
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentState:
    """Global state object shared across all agent nodes."""

    # --- INPUTS ---
    job_description_text: str = ""
    resume_file_path: str = ""
    resume_file_type: str = ""  # "pdf" | "docx"
    resume_filename: str = ""  # original filename for display
    requisition_id: str = ""  # Talent ID from requisition CSV

    # --- PROCESSED FILES ---
    resume_pdf_path: str = ""
    resume_base64: Optional[str] = None
    resume_extracted_text: str = ""
    resume_markdown: str = ""  # Markdown version of resume (used for OpenAI)

    # --- EXTRACTION ---
    jd_requirements: Optional[dict] = None

    # --- EVALUATION ---
    evaluation: Optional[dict] = None
    overall_score: float = 0.0
    category_scores: Optional[dict] = None
    matched_requirements: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    deal_breaker_status: str = ""

    # --- VERIFICATION ---
    verification_report: list = field(default_factory=list)
    supported_claims: list = field(default_factory=list)
    unsupported_claims: list = field(default_factory=list)

    # --- SEVERITY ---
    severity_report: list = field(default_factory=list)
    has_critical: bool = False
    has_moderate: bool = False
    all_minor: bool = False

    # --- RECTIFICATION ---
    hallucination_history: list = field(default_factory=list)
    patch_log: list = field(default_factory=list)

    # --- CONTROL ---
    attempt_count: int = 0
    current_model: str = "claude-sonnet-4-6"
    current_node: str = ""
    path_taken: list = field(default_factory=list)

    # --- CONTACT INFO (extracted from resume text) ---
    candidate_name: str = ""
    candidate_email: str = ""
    candidate_phone: str = ""
    candidate_total_experience: str = ""
    candidate_company: str = ""
    candidate_location: str = ""
    candidate_skill: str = ""

    # --- OUTPUT ---
    final_evaluation: Optional[dict] = None
    final_score: float = 0.0
    confidence: str = ""
    status: str = ""
    total_attempts: int = 0
    verification_summary: str = ""

    # --- OBSERVABILITY ---
    trace_id: str = field(default_factory=lambda: f"ats-run-{uuid.uuid4().hex[:12]}")
    run_metadata: dict = field(default_factory=dict)
    node_logs: list = field(default_factory=list)
    token_usage: dict = field(default_factory=lambda: {"input": 0, "output": 0, "total": 0})
    total_latency_ms: int = 0
    total_cost_estimate: float = 0.0
    timestamp_start: float = field(default_factory=time.time)

    # --- ERROR ---
    error: Optional[str] = None

    def log_node(self, log_entry: dict):
        """Append a trace log entry for a node execution."""
        self.node_logs.append(log_entry)
        if "input_tokens" in log_entry and "output_tokens" in log_entry:
            self.token_usage["input"] += log_entry.get("input_tokens", 0)
            self.token_usage["output"] += log_entry.get("output_tokens", 0)
            self.token_usage["total"] = self.token_usage["input"] + self.token_usage["output"]
        if "latency_ms" in log_entry:
            self.total_latency_ms += log_entry["latency_ms"]
        if "cost_estimate" in log_entry:
            self.total_cost_estimate += log_entry.get("cost_estimate", 0.0)

    def extract_contact_info(self):
        """Extract candidate name, email, and phone from resume text."""
        text = self.resume_extracted_text or ""

        # Email
        email_match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
        if email_match:
            self.candidate_email = email_match.group(0)

        # Phone — various formats
        phone_match = re.search(
            r'(?:\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}', text
        )
        if phone_match:
            self.candidate_phone = phone_match.group(0).strip()

        # Name — first non-empty line of resume (usually the candidate name)
        if not self.candidate_name:
            for line in text.split('\n'):
                line = line.strip()
                if line and not re.match(r'^(http|www\.|[a-zA-Z0-9._%+\-]+@)', line) and len(line) < 80:
                    self.candidate_name = line
                    break

        # Fallback: derive name from filename
        if not self.candidate_name and self.resume_filename:
            import os
            name = os.path.splitext(self.resume_filename)[0]
            name = re.sub(r'[_\-]+', ' ', name)
            name = re.sub(r'(?i)\b(resume|cv)\b', '', name).strip()
            self.candidate_name = name.title() if name else self.resume_filename

    def to_final_output(self) -> dict:
        """Package the final result with all metadata."""
        self.extract_contact_info()
        return {
            "requisition_id": self.requisition_id,
            "candidate_contact": {
                "name": self.candidate_name,
                "email": self.candidate_email,
                "phone": self.candidate_phone,
                "total_experience": self.candidate_total_experience,
                "company": self.candidate_company,
                "location": self.candidate_location,
                "skill": self.candidate_skill,
            },
            "candidate_evaluation": {
                "overall_score": self.final_score or self.overall_score,
                "category_scores": self.category_scores or {},
                "matched_requirements": self.matched_requirements,
                "gaps_and_missing": self.gaps,
                "deal_breaker_check": {
                    "status": self.deal_breaker_status,
                    "explanation": (self.evaluation.get("deal_breaker_check") or {}).get("explanation", "") if self.evaluation else ""
                },
                "summary": self.evaluation.get("summary", "") if self.evaluation else ""
            },
            "reliability_metadata": {
                "confidence": self.confidence,
                "status": self.status,
                "total_attempts": self.attempt_count,
                "hallucinations_caught": len(self.hallucination_history),
                "verification_rate": (
                    len(self.supported_claims) / max(len(self.supported_claims) + len(self.unsupported_claims), 1)
                ),
                "rectification_method": self.patch_log[-1].get("method", "none") if self.patch_log else "none",
                "score_adjustment": {
                    "original_score": self.patch_log[0].get("score_before", self.overall_score) if self.patch_log else self.overall_score,
                    "final_score": self.final_score or self.overall_score,
                    "delta": round((self.final_score or self.overall_score) - (self.patch_log[0].get("score_before", self.overall_score) if self.patch_log else self.overall_score), 2)
                }
            },
            "audit_trail": {
                "trace_id": self.trace_id,
                "path_taken": self.path_taken,
                "node_logs": self.node_logs,
                "total_tokens": self.token_usage,
                "total_cost_estimate": round(self.total_cost_estimate, 4),
                "total_latency_ms": self.total_latency_ms,
                "model_used": self.current_model,
                "timestamp_start": self.timestamp_start,
                "timestamp_end": time.time()
            },
            "resume_filename": self.resume_filename
        }
