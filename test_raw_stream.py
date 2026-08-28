import asyncio
import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

async def test_stream():
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "openrouter/free",
        "messages": [{"role": "user", "content": "moi"}],
        "stream": True,
        "stream_options": {"include_usage": True}
    }
    headers = {"Authorization": f"Bearer {key}", "HTTP-Referer": "http://localhost:8002"}
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    print("DATA:", line[:120])

if __name__ == "__main__":
    asyncio.run(test_stream())
