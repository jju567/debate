import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

async def main():
    async with httpx.AsyncClient() as client:
        res = await client.get("https://openrouter.ai/api/v1/models")
        if res.status_code == 200:
            models = res.json().get("data", [])
            for m in models:
                mid = m["id"]
                if mid.startswith("anthropic/") or mid.startswith("openai/") or mid.startswith("google/") or mid.startswith("deepseek/"):
                    p = m.get("pricing", {})
                    print(f"{mid:50} | Prompt: ${float(p.get('prompt', 0))*1e6:.2f}/M | Compl: ${float(p.get('completion', 0))*1e6:.2f}/M")

if __name__ == "__main__":
    asyncio.run(main())
