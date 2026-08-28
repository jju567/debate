import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("OPENROUTER_API_KEY")
print(f"API Key found: {bool(key)}, length: {len(key) if key else 0}")

async def main():
    async with httpx.AsyncClient() as client:
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "messages": [{"role": "user", "content": "Sano 'testi ok' suomeksi."}],
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8002",
            "X-Title": "AI Design Studio",
        }
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=30.0)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
