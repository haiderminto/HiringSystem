# Agentic Hire

An AI-powered hiring system that automates the end-to-end recruitment pipeline — from job requisition selection and resume evaluation to AI voice screening of candidates.

## Agent Capabilities

### 1. Intelligent Resume Evaluation (10-Node Agentic Pipeline)

The core of Agentic Hire is a multi-step agentic pipeline that evaluates resumes with built-in hallucination detection and self-correction:

| Node | Purpose |
|------|---------|
| **File Intake** | Validates and prepares resume files (PDF/DOCX) for LLM processing |
| **JD Extraction** | Parses job descriptions into structured requirements (skills, experience, certifications, deal-breakers) |
| **Resume Evaluation** | Scores resumes (1-10) against JD requirements with evidence-based matching |
| **Evidence Verification** | Audits every matched claim against the actual resume text |
| **Severity Classification** | Classifies unsupported claims as Critical, Moderate, or Minor |
| **Router** | Decides next action: accept, patch score, re-evaluate, or escalate |
| **Patch & Recalculate** | Surgically removes unsupported claims and recalculates scores |
| **Re-Evaluation** | Full re-evaluation with anti-hallucination constraints injected |
| **Escalation** | Handles persistent hallucinations via model upgrade, deterministic scoring, or human review flagging |
| **Final Output** | Packages results with confidence levels, audit trails, and token/cost tracking |

**Key differentiator:** The agent does not blindly trust its own output. It verifies every claim, catches fabricated evidence, and self-corrects — producing reliable, auditable evaluations.

### 2. Job Requisition Integration

- Loads job requisitions from a CSV file (configurable path via `.env`)
- Users select a requisition from an interactive table in the UI
- Job descriptions are auto-composed from Skill, Designation, Location, Grade, and JD fields
- Results are tagged with the Requisition ID for tracking

### 3. Candidate Contact Extraction

- Automatically extracts candidate name, email, phone number from resume text
- LLM-powered extraction of total experience, current company, location, and primary skills
- All fields included in evaluation results and CSV export

### 4. AI Voice Screening

- Integrates with ElevenLabs Conversational AI for automated voice screening interviews
- Sequential auto-execution: screens candidates one by one with configurable delays
- Real-time status tracking with start/stop controls
- Fetches transcripts and evaluation criteria results after each interview

### 5. Results Persistence

- **JSON**: Full evaluation results with audit trails saved to `results/` directory
- **CSV**: Structured export with columns: Talent ID, Candidate Name, Email, Phone, Skill, Total Experience, Location, Profile Match Score, Summary, Deal Breaker status, Hard/Soft Skill Scores
- CSV output path configurable via `RESUME_RESULTS_CSV` in `.env`

### 6. Real-Time Streaming UI

- NDJSON streaming from backend to frontend for real-time progress updates
- Live progress log with color-coded status messages
- Results appear in the table as each resume completes evaluation
- Expandable detail panels with category scores, matched requirements, gaps, and audit trails

## Tech Stack

### Backend
| Technology | Purpose |
|-----------|---------|
| **Python 3.10+** | Core runtime |
| **FastAPI** | Web framework with async support and NDJSON streaming |
| **Uvicorn** | ASGI server |
| **Pydantic** | Settings management and data validation |

### AI / LLM
| Technology | Purpose |
|-----------|---------|
| **Anthropic Claude** (claude-sonnet / claude-opus) | Primary LLM provider for resume evaluation |
| **OpenAI GPT-4o** | Alternative LLM provider |
| **ElevenLabs Conversational AI** | Voice screening interviews via WebRTC |

### Document Processing
| Technology | Purpose |
|-----------|---------|
| **PyMuPDF (fitz)** | PDF text extraction and validation |
| **python-docx** | DOCX parsing |
| **docx2pdf** | DOCX to PDF conversion |
| **mammoth** | DOCX to Markdown conversion |

### Observability
| Technology | Purpose |
|-----------|---------|
| **Arize Phoenix** | LLM tracing and monitoring |
| **OpenTelemetry** | Distributed tracing framework |
| **OpenInference** | Instrumentation for Anthropic and OpenAI calls |

### Frontend
| Technology | Purpose |
|-----------|---------|
| **Vanilla JavaScript** | No frameworks — lightweight, fast |
| **HTML5 / CSS3** | Responsive UI with CSS custom properties |

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure `.env`:
   ```env
   LLM_PROVIDER=openai                # or "anthropic"
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   JOB_REQUISITION_CSV=D:\path\to\Job_Requisition_details.csv
   RESUME_RESULTS_CSV=D:\path\to\Resume_Evaluation_Results.csv
   ```
4. Run the server:
   ```bash
   python main.py
   ```
5. Open `http://localhost:8000` in your browser

## Future Enhancements

### Database Persistence
Replace file-based CSV/JSON storage with a relational database (PostgreSQL or SQL Server) to enable:
- Centralized storage of all evaluation results across requisitions
- Historical tracking of candidate evaluations over time
- Multi-user concurrent access without file locking issues
- Structured queries (e.g., "show all candidates scored above 7 for requisition X")
- Audit log persistence with full traceability

### Anthropic Batch Processing API
Leverage the [Anthropic Message Batches API](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing) to dramatically reduce costs:
- **50% cost reduction**: Batch API pricing is half of standard API pricing
- **Bulk resume processing**: Submit all resumes in a single batch request instead of sequential calls
- **Ideal for high-volume hiring**: Process hundreds of resumes per requisition at scale
- **Asynchronous processing**: Submit batch, poll for completion, retrieve results — no need for real-time streaming when processing large volumes
- **Implementation approach**: Add a "Batch Evaluate" mode alongside the existing real-time mode, where users can submit a folder and return later for results

### Additional Planned Enhancements
- **Interview Scheduling Integration**: Connect the "Schedule Interview" button to calendar APIs (Google Calendar, Outlook)
- **Multi-Requisition Batch Processing**: Evaluate the same resume pool against multiple requisitions simultaneously
- **Candidate De-duplication**: Detect and merge duplicate candidates across requisitions
- **Recruiter Dashboard**: Analytics view showing pipeline metrics, pass rates, and bottleneck identification
- **Email Notifications**: Automated candidate communication for screening invitations and status updates

## Architecture

```
                    ┌─────────────────────────────────┐
                    │          Frontend (UI)           │
                    │   index.html / app.js / CSS      │
                    └──────────────┬──────────────────┘
                                   │ NDJSON Stream
                    ┌──────────────▼──────────────────┐
                    │       FastAPI Backend            │
                    │         main.py                  │
                    └──────────────┬──────────────────┘
                                   │
              ┌────────────────────▼────────────────────┐
              │         10-Node Agentic Pipeline         │
              │                                         │
              │  FILE_INTAKE → JD_EXTRACTION             │
              │       → RESUME_EVALUATION                │
              │       → EVIDENCE_VERIFICATION            │
              │       → SEVERITY_CLASSIFICATION          │
              │       → ROUTER ──┬── PATCH_RECALCULATE   │
              │                  ├── RE_EVALUATION        │
              │                  └── ESCALATION           │
              │       → FINAL_OUTPUT                     │
              └────────────────────┬────────────────────┘
                                   │
                 ┌─────────────────┼─────────────────┐
                 ▼                 ▼                  ▼
          LLM Provider      ElevenLabs         Arize Phoenix
        (Claude / GPT-4o)   (Voice Screen)     (Tracing)
```

## License

Internal use — Hackathon Team 5
