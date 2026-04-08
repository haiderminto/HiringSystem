# ATS Resume Evaluator - Setup Guide

## Critical: Secure Your API Keys

The `.env` file contains exposed API keys. **These must be rotated immediately.**

1. Visit https://console.anthropic.com/account/billing/overview and regenerate your Anthropic API key
2. Visit https://platform.openai.com/account/billing/overview and regenerate your OpenAI API key
3. Update `.env` with the new keys

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure `.env`

Edit `.env` and set your API keys:

```env
# Choose "anthropic" or "openai"
LLM_PROVIDER=anthropic

# Anthropic Configuration (required if using anthropic)
ANTHROPIC_API_KEY=sk-ant-...your-key-here...
DEFAULT_MODEL=claude-sonnet-4-6
ESCALATION_MODEL=claude-opus-4-6

# OpenAI Configuration (required if using openai)
OPENAI_API_KEY=sk-proj-...your-key-here...
OPENAI_DEFAULT_MODEL=gpt-4o

ENABLE_MODEL_ESCALATION=false
MAX_EVALUATION_ATTEMPTS=2
UPLOAD_DIR=uploads
RESULTS_DIR=results
```

### 3. Verify Setup

```bash
python test_imports.py
```

### 4. Start the Server

```bash
python main.py
```

Then open http://localhost:8000 in your browser.

## Troubleshooting

### "Bad Gateway" Error

If you get a 502 Bad Gateway error:

1. **Check dependencies installed:**
   ```bash
   pip install -r requirements.txt
   python test_imports.py
   ```

2. **Check API key is set:**
   ```bash
   echo $OPENAI_API_KEY  # or ANTHROPIC_API_KEY
   ```

3. **Check logs** — run the server with:
   ```bash
   python main.py 2>&1 | tee server.log
   ```

4. **Verify file permissions** — ensure you can write to `uploads/` directory

### Resume Processing Hangs

- Verify your API key has correct permissions
- Check your API account has available credits
- Ensure resume files are valid PDF or DOCX

## Architecture Notes

- **Provider Support**: Anthropic (PDF document blocks) + OpenAI (resume markdown)
- **Resume Upload**: Stored in `uploads/YYYYMMDD_HHMMSS/` folders (never deleted)
- **Results**: Saved as JSON in the same upload folder
- **Streaming**: Frontend receives real-time NDJSON updates as resumes process

## First Run

1. Paste a job description
2. Upload 1-3 sample resumes (PDF or DOCX)
3. Click "Evaluate Resumes"
4. Watch progress in real time
5. Results ranked by overall score
