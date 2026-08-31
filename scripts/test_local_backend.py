import asyncio
import httpx

async def test_backend():
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:8002/api/config")
        print("Backend /api/config status:", resp.status_code)
        print("Palautetut agentit:", list(resp.json()["participants"].keys()))
        print("Editori:", resp.json()["editor_model"])

if __name__ == "__main__":
    asyncio.run(test_backend())
