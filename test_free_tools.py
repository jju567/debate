import asyncio
import os
import httpx
from dotenv import load_dotenv
from tools import TOOLS

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

async def main():
    async with httpx.AsyncClient() as client:
        # Testataan tukeeko ilmainen malli tools-parametria
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": "openrouter/free",
            "messages": [{"role": "user", "content": "moi"}],
            "tools": TOOLS
        }
        headers = {"Authorization": f"Bearer {key}", "HTTP-Referer": "http://localhost:8002"}
        resp = await client.post(url, json=payload, headers=headers, timeout=20.0)
        print("Tools-testi Status:", resp.status_code)
        print("Vastaus:", resp.text[:400])

if __name__ == "__main__":
    asyncio.run(main())
