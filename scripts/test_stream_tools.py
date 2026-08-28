import asyncio
import os
import json
import httpx
from dotenv import load_dotenv
from tools import TOOLS

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

async def test_tool_stream():
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "openrouter/free",
        "messages": [
            {"role": "system", "content": "Sinulla on käytössäsi execute_python ja eval_python_expression työkalut. Kun pyydetään laskemaan tai ajamaan koodia, kutsu vastaavaa työkalua."},
            {"role": "user", "content": "Käytä eval_python_expression työkalua ja laske 123 * 456."}
        ],
        "tools": TOOLS,
        "stream": True
    }
    headers = {"Authorization": f"Bearer {key}", "HTTP-Referer": "http://localhost:8002"}
    
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            print("Status:", resp.status_code)
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    chunk = line[5:].strip()
                    if chunk != "[DONE]":
                        try:
                            d = json.loads(chunk)
                            delta = d["choices"][0]["delta"]
                            if "tool_calls" in delta:
                                print("TOOL_CALL DELTA:", delta["tool_calls"])
                            if "content" in delta and delta["content"]:
                                print("CONTENT:", delta["content"])
                        except Exception as e:
                            pass

if __name__ == "__main__":
    asyncio.run(test_tool_stream())
