"""
ElevenLabs WebRTC Candidate Screening — Link-Based Flow

Usage:
  python screening_call.py generate "John Doe"                # serve locally + open browser
  python screening_call.py generate "John Doe" --port 9000    # custom port
  python screening_call.py results                             # fetch latest interview results
  python screening_call.py results --conv-id <id>             # fetch specific interview

pip install elevenlabs python-dotenv requests
"""

import os
import re
import json
import argparse
import subprocess
import threading
import webbrowser
import requests
from http.server import HTTPServer, SimpleHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

# -- Credentials (set these in .env) ------------------------------------------
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
AGENT_ID           = os.getenv("AGENT_ID", "agent_8501knnrs323f6ssjhk87ft80w7w")

BASE_URL = "https://api.elevenlabs.io/v1"
HEADERS  = {
    "xi-api-key": ELEVENLABS_API_KEY,
    "Content-Type": "application/json"
}


# -- Step 1: Create HTML page and serve it locally ----------------------------
def create_html_page(candidate_name: str) -> str:
    """Write a self-contained HTML file using the ElevenLabs widget (agent-id, no signing needed)."""
    safe_name = candidate_name.replace(" ", "_").lower()
    filename  = f"interview_{safe_name}.html"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Screening Interview — {candidate_name}</title>
  <style>
    body {{
      font-family: sans-serif;
      max-width: 640px;
      margin: 80px auto;
      text-align: center;
      color: #333;
    }}
    p {{ color: #555; line-height: 1.7; }}
    elevenlabs-convai {{ margin-top: 32px; display: block; }}
  </style>
</head>
<body>
  <h1>Screening Interview</h1>
  <p>
    Hello, <strong>{candidate_name}</strong>.<br />
    Click the button below, allow microphone access, and begin when ready.
  </p>
  <p><em>Speak clearly. The interview will end automatically when complete.</em></p>

  <elevenlabs-convai agent-id="{AGENT_ID}"></elevenlabs-convai>
  <script src="https://elevenlabs.io/convai-widget/index.js" async></script>
</body>
</html>"""

    with open(filename, "w") as f:
        f.write(html)

    return filename


def start_serveo_tunnel(port: int):
    """Start a serveo.net SSH reverse tunnel. Returns (public_url, process)."""
    proc = subprocess.Popen(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-R", f"80:localhost:{port}", "serveo.net"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    for line in proc.stdout:
        print(f"[serveo] {line.rstrip()}")   # show raw output for debugging
        match = re.search(r"Forwarding HTTP traffic from (https?://\S+)", line)
        if match:
            return match.group(1), proc
    return None, proc


def serve_and_open(filename: str, port: int):
    """Serve the interview HTML via a local HTTP server with a serveo.net public tunnel."""
    folder    = os.path.dirname(os.path.abspath(filename))
    page      = os.path.basename(filename)
    local_url = f"http://localhost:{port}/{page}"

    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=folder, **kwargs)
        def log_message(self, *_):
            pass

    server = HTTPServer(("", port), QuietHandler)

    # Start serveo tunnel in background thread so it doesn't block the server
    tunnel_proc = None
    def launch_tunnel():
        nonlocal tunnel_proc
        print("Starting serveo tunnel...")
        public_base, tunnel_proc = start_serveo_tunnel(port)
        if public_base:
            candidate_url = f"{public_base}/{page}"
            print(f"\nLocal URL:      {local_url}")
            print(f"Candidate URL:  {candidate_url}  ← share this with the candidate\n")
        else:
            print("  Could not get serveo URL — share the local URL manually.")

    threading.Thread(target=launch_tunnel, daemon=True).start()

    # Open the local URL in your own browser after a short delay
    threading.Timer(1.5, lambda: webbrowser.open(local_url)).start()

    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        if tunnel_proc:
            tunnel_proc.terminate()


# -- Step 3: Fetch conversation results --------------------------------------─
def get_latest_conv_id() -> str:
    """Return the most recently completed conversation ID for this agent."""
    url      = f"{BASE_URL}/convai/conversations"
    response = requests.get(url, headers=HEADERS, params={"agent_id": AGENT_ID, "page_size": 1})

    if response.status_code != 200:
        print(f"Failed to list conversations: {response.status_code}")
        print(response.text)
        exit(1)

    convs = response.json().get("conversations", [])
    if not convs:
        print("No conversations found for this agent yet.")
        exit(1)

    return convs[0].get("conversation_id")


def fetch_conversation(conv_id: str) -> dict:
    url      = f"{BASE_URL}/convai/conversations/{conv_id}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"Error fetching conversation {conv_id}: {response.status_code}")
        print(response.text)
        exit(1)

    return response.json()


# -- Step 4: Display & save results ------------------------------------------─
def parse_and_display(data: dict):
    print("\n-- Transcript ---------------------------------------")
    transcript = data.get("transcript", [])

    if not transcript:
        print("  No transcript available yet.")
    else:
        for turn in transcript:
            role    = turn.get("role", "unknown").upper()
            message = turn.get("message", "")
            print(f"  [{role}]: {message}")

    analysis = data.get("analysis", {})

    print("\n-- Summary ------------------------------------------")
    print(f"  {analysis.get('transcript_summary', 'No summary available.')}")

    print("\n-- Evaluation Criteria ------------------------------")
    criteria = analysis.get("evaluation_criteria_results", {})
    if criteria:
        for name, result in criteria.items():
            verdict   = result.get("result", "N/A")
            rationale = result.get("rationale", "")
            print(f"  {name}: {verdict}")
            if rationale:
                print(f"    → {rationale}")
    else:
        print("  No evaluation criteria results.")
        print("  Tip: Add evaluation criteria in the ElevenLabs dashboard -> your agent -> Analysis tab.")

    print("\n-- Data Collected -----------------------------------")
    collected = analysis.get("data_collection_results", {})
    if collected:
        for name, result in collected.items():
            print(f"  {name}: {result.get('value', 'N/A')}")
    else:
        print("  No data collection results.")

    return transcript, analysis


def save_result(conv_id: str, transcript: list, analysis: dict, candidate_name: str = ""):
    output   = {"conversation_id": conv_id, "transcript": transcript, "analysis": analysis}
    if candidate_name:
        safe = candidate_name.replace(" ", "_").lower()
        filename = f"result_{safe}.json"
    else:
        filename = f"result_{conv_id}.json"
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResult saved to: {filename}")


# -- Main ----------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ElevenLabs WebRTC Screening — Link-Based")
    sub    = parser.add_subparsers(dest="command", required=True)

    # generate: create interview page and serve it locally
    gen = sub.add_parser("generate", help="Generate and serve an interview page for a candidate")
    gen.add_argument("candidate_name", help='Candidate full name, e.g. "Jane Smith"')
    gen.add_argument("--port", type=int, default=8000, help="Local port to serve on (default: 8000)")

    # results: pull transcript + analysis for a completed interview
    res = sub.add_parser("results", help="Fetch results for a completed interview")
    res.add_argument("--conv-id", help="Conversation ID (omit to use the most recent)")
    res.add_argument("--name", help='Candidate name to use in the filename, e.g. "Jane Smith"')

    args = parser.parse_args()

    if args.command == "generate":
        filename = create_html_page(args.candidate_name)
        serve_and_open(filename, args.port)

    elif args.command == "results":
        conv_id              = args.conv_id or get_latest_conv_id()
        data                 = fetch_conversation(conv_id)
        transcript, analysis = parse_and_display(data)
        save_result(conv_id, transcript, analysis, args.name or "")

        proceed = analysis.get("evaluation_criteria_results", {}).get("proceed_to_next_round", {})
        verdict = proceed.get("result", "N/A — add 'proceed_to_next_round' criterion in ElevenLabs dashboard")
        print(f"\nProceed to Next Round: {verdict}")
