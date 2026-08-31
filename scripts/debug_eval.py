import asyncio
import os
import httpx
from dotenv import load_dotenv
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm import stream_chat
from tools import TOOLS
from tool_executor import execute_tool_call

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

async def test_kolli_eval():
    async with httpx.AsyncClient() as client:
        messages = [
            {"role": "system", "content": "Olet Kolli, tehokas pääkoodari. Käytä työkalua eval_python_expression laskeaksesi vastauksen."},
            {"role": "user", "content": "Laske eval_python_expression -työkalulla: math.sqrt(2048) * 10"}
        ]
        
        print("=== 1. Kutsu stream_chat ===")
        tool_calls_complete = []
        async for event in stream_chat(client, "openai/gpt-4o-mini", messages, key, tools=TOOLS):
            print("EVENT:", event["type"])
            if event["type"] == "text":
                print(event["text"], end="", flush=True)
            elif event["type"] == "tool_calls_complete":
                tool_calls_complete = event["tool_calls"]
                print("\n[Tool calls complete]:", tool_calls_complete)

        if tool_calls_complete:
            print("\n=== 2. Suoritetaan työkalut ===")
            for tc in tool_calls_complete:
                fn = tc.get("function", {})
                fn_name = fn.get("name")
                import json
                args = json.loads(fn.get("arguments", "{}"))
                print("fn_name:", fn_name, "args:", args)
                chat_msg, raw_res = execute_tool_call(fn_name, args)
                print("chat_msg:", chat_msg)
                print("raw_res:", raw_res)

if __name__ == "__main__":
    asyncio.run(test_kolli_eval())
