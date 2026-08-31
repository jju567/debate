import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

test_panel = [
    ("Seppo (GPT-4o)", "openai/gpt-4o"),
    ("Matti (DeepSeek R1 Reasoning)", "deepseek/deepseek-r1"),
    ("Aki (Gemini 2.5 Flash)", "google/gemini-2.5-flash"),
    ("Kolli (GPT-4o Mini)", "openai/gpt-4o-mini"),
    ("Legal (DeepSeek Chat)", "deepseek/deepseek-chat"),
    ("Editori (Claude Sonnet 4.5)", "anthropic/claude-sonnet-4.5"),
]

async def main():
    async with httpx.AsyncClient() as client:
        for name, m in test_panel:
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {
                "model": m,
                "messages": [{"role": "user", "content": "Vastaa lyhyesti: 'Malli toimii'."}]
            }
            headers = {
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "http://localhost:8002",
                "X-Title": "AI Design Studio",
                "Content-Type": "application/json"
            }
            try:
                resp = await client.post(url, json=payload, headers=headers, timeout=25.0)
                print(f"{name:32} [{m:30}] -> Status {resp.status_code}")
                if resp.status_code == 200:
                    ans = resp.json()["choices"][0]["message"]["content"].strip()
                    print(f"   Vastaus: {ans[:70]}")
                else:
                    print(f"   Virhe: {resp.text[:120]}")
            except Exception as e:
                print(f"   Poikkeus: {e}")

if __name__ == "__main__":
    asyncio.run(main())
