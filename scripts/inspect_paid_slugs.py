import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

test_models = [
    "anthropic/claude-3.5-sonnet-20241022",
    "anthropic/claude-3.7-sonnet",
    "anthropic/claude-3-5-sonnet",
    "google/gemini-2.5-flash",
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-flash-1.5",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-coder-32b-instruct"
]

async def main():
    async with httpx.AsyncClient() as client:
        # Tarkistetaan myös saatavilla olevat mallit
        res = await client.get("https://openrouter.ai/api/v1/models")
        if res.status_code == 200:
            all_models = [m["id"] for m in res.json().get("data", [])]
            claude_models = [m for m in all_models if "claude" in m]
            gemini_models = [m for m in all_models if "gemini" in m]
            print("Löydetyt Claude-mallit:", claude_models[:5])
            print("Löydetyt Gemini-mallit:", gemini_models[:5])

        for m in ["anthropic/claude-3.7-sonnet", "google/gemini-2.5-flash", "openai/gpt-4o", "openai/gpt-4o-mini", "deepseek/deepseek-chat"]:
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {"model": m, "messages": [{"role": "user", "content": "Sano 'ok'."}]}
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            resp = await client.post(url, json=payload, headers=headers, timeout=15.0)
            print(f"Malli {m}: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(main())
