"""OpenRouter-streamausapuri.

OpenRouter tarjoaa OpenAI-yhteensopivan chat completions -rajapinnan, jossa
usealla mallilla on sama muoto. Streamaus tulee SSE-muodossa (rivit "data: {...}").
"""

import json

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(Exception):
    """OpenRouter-kutsu epäonnistui."""


async def stream_chat(client: httpx.AsyncClient, model: str, messages: list, api_key: str, tools: list | None = None):
    """Async-generaattori, joka tuottaa tekstipaloja ja työkalukutsuja yhdeltä mallilta.

    Heittää LLMError-poikkeuksen jos kutsu epäonnistuu.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        payload["tools"] = tools

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # OpenRouter suosittelee näitä tunnistautumisen/tilastoinnin vuoksi.
        "HTTP-Referer": "http://localhost:8002",
        "X-Title": "AI Design Studio",
    }

    async with client.stream(
        "POST", OPENROUTER_URL, json=payload, headers=headers, timeout=180.0
    ) as resp:
        if resp.status_code != 200:
            body = await resp.aread()
            raise LLMError(f"HTTP {resp.status_code}: {body.decode(errors='replace')[:400]}")

        async for line in resp.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            
            # Check for usage stats in stream chunk
            usage = obj.get("usage")
            if usage:
                yield {"type": "usage", "usage": usage}

            choices = obj.get("choices") or [{}]
            delta = choices[0].get("delta") or {}
            
            # Handle text content
            chunk = delta.get("content")
            if chunk:
                yield {"type": "text", "text": chunk}

            # Handle tool calls
            tool_calls = delta.get("tool_calls")
            if tool_calls:
                yield {"type": "tool_calls", "tool_calls": tool_calls}


