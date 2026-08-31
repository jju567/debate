import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

test_models = [
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.3-70b-instruct",
    "deepseek/deepseek-chat"
]

async def main():
    async with httpx.AsyncClient() as client:
        for m in test_models:
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {"model": m, "messages": [{"role": "user", "content": "Sano 'testi ok' suomeksi."}]}
            headers = {
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "http://localhost:8002",
                "X-Title": "AI Design Studio",
                "Content-Type": "application/json"
            }
            try:
                resp = await client.post(url, json=payload, headers=headers, timeout=20.0)
                print(f"Malli {m}: Status {resp.status_code}")
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    print(f" -> Vastaus: {content.strip()}")
                else:
                    print(f" -> Virhe: {resp.text}")
            except Exception as e:
                print(f" -> Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
