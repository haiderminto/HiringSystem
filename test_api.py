"""Quick API key & model validation."""
import os, sys
from dotenv import load_dotenv
load_dotenv()

key = ''#os.getenv("ANTHROPIC_API_KEY", "")
print(f"Key prefix: {key[:20]}...")
print(f"Key length: {len(key)}")

import anthropic
print(f"anthropic SDK version: {anthropic.__version__}")

client = anthropic.Anthropic(api_key=key)
for model in ["claude-sonnet-4-6", "claude-opus-4-6"]:
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Say hi"}],
        )
        print(f"[OK] {model} -> {resp.content[0].text}")
    except anthropic.AuthenticationError as e:
        print(f"[FAIL] {model} -> AUTH ERROR: {e}")
    except anthropic.NotFoundError as e:
        print(f"[FAIL] {model} -> MODEL NOT FOUND: {e}")
    except anthropic.BadRequestError as e:
        print(f"[FAIL] {model} -> BAD REQUEST: {e}")
    except anthropic.APIStatusError as e:
        print(f"[FAIL] {model} -> API STATUS {e.status_code}: {e.message}")
    except Exception as e:
        print(f"[FAIL] {model} -> {type(e).__name__}: {e}")
