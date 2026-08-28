import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

test_models = [
    "openrouter/free",
    "google/gemma-4-31b-it:free",
    "minimax/minimax-m2.7:free",
    "z-ai/glm-5.2:free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
]

async def main():
    async with httpx.AsyncClient() as client:
        for m in test_models:
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {"model": m, "messages": [{"role": "user", "content": "Sano 'toimii' suomeksi."}]}
            headers = {"Authorization": f"Bearer {key}", "HTTP-Referer": "http://localhost:8002"}
            resp = await client.post(url, json=payload, headers=headers, timeout=20.0)
            print(f"Malli {m}: Status {resp.status_code}")
            if resp.status_code == 200:
                print(" -> Vastaus:", resp.json()["choices"][0]["message"]["content"][:60])
            else:
                print(" -> Virhe:", resp.text[:100])

if __name__ == "__main__":
    asyncio.run(main())
