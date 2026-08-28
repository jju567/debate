import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("OPENROUTER_API_KEY")

async def main():
    async with httpx.AsyncClient() as client:
        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {key}"}
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            free_models = [m["id"] for m in models if ":free" in m["id"] or (m.get("pricing", {}).get("prompt") == "0" and m.get("pricing", {}).get("completion") == "0")]
            print("Aktiviiset ilmaiset mallit OpenRouterissa:")
            for m in free_models:
                print(" -", m)
        else:
            print("Virhe:", resp.status_code, resp.text)

if __name__ == "__main__":
    asyncio.run(main())
