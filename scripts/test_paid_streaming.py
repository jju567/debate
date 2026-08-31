import asyncio
import os
import json
import httpx
from dotenv import load_dotenv
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import TOOLS

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

async def test_full_flow():
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "http://localhost:8002",
        "X-Title": "AI Design Studio",
        "Content-Type": "application/json"
    }
    
    # Testataan Kolli koodaus / työkaluilla
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Olet Kolli, tehokas Python-koodari. Käytä työkalua eval_python_expression tai laske vastaus."},
            {"role": "user", "content": "Laske paljonko on 256 * 1024?"}
        ],
        "tools": TOOLS,
        "stream": True,
        "stream_options": {"include_usage": True}
    }
    
    print("Testataan streamaus & token usage Kolli (GPT-4o-mini)...")
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            print("HTTP Status:", resp.status_code)
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        print("\n[STREAM VALMIS]")
                        break
                    try:
                        d = json.loads(chunk)
                        if "choices" in d and d["choices"]:
                            delta = d["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                print(delta["content"], end="", flush=True)
                        if "usage" in d and d["usage"]:
                            print(f"\n[USAGE TULI]: {d['usage']}")
                    except Exception:
                        pass

if __name__ == "__main__":
    asyncio.run(test_full_flow())
