"""OpenRouter-streamausapuri.

OpenRouter tarjoaa OpenAI-yhteensopivan chat completions -rajapinnan, jossa
usealla mallilla on sama muoto. Streamaus tulee SSE-muodossa (rivit "data: {...}").
"""

import json
import logging
import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
logger = logging.getLogger("debate.llm")
logger.setLevel(logging.INFO)


class LLMError(Exception):
    """OpenRouter-kutsu epäonnistui."""


async def stream_chat(
    client: httpx.AsyncClient,
    model: str,
    messages: list,
    api_key: str,
    tools: list | None = None,
    allow_fallback: bool = True,
    fallback_model: str = "openrouter/free",
):
    """Async-generaattori, joka tuottaa tekstipaloja ja työkalukutsuja yhdeltä mallilta.

    Kokoaa streamaavat tool_calls-deltalohkot oikein indeksin mukaan.
    Jos pyyntö epäonnistuu saldon loppumiseen (HTTP 402) ja allow_fallback=True,
    siirtyy automaattisesti käyttämään ilmaista varamallia (fallback_model).
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

    timeout_config = httpx.Timeout(180.0, connect=30.0, read=180.0, write=30.0)
    async with client.stream(
        "POST", OPENROUTER_URL, json=payload, headers=headers, timeout=timeout_config
    ) as resp:
        if resp.status_code in (402, 429) and allow_fallback and model != fallback_model:
            body = await resp.aread()
            err_text = body.decode(errors="replace")[:400]
            logger.warning(
                f"OpenRouter HTTP {resp.status_code} ({model}): Saldo tai limiitti loppu. Siirrytään ilmaiseen varamalliin ({fallback_model}). Virhe: {err_text}"
            )
            # Ilmoitetaan varamallin aktivoinnista
            yield {
                "type": "fallback_triggered",
                "original_model": model,
                "fallback_model": fallback_model,
                "reason": f"HTTP {resp.status_code} - Saldo tai limiitti loppu. Siirrytty ilmaismalliin.",
            }
            # Kutsutaan varamallia ilman lisä-fallbackia silmukan välttämiseksi
            async for fallback_event in stream_chat(
                client=client,
                model=fallback_model,
                messages=messages,
                api_key=api_key,
                tools=tools,
                allow_fallback=False,
            ):
                yield fallback_event
            return

        if resp.status_code != 200:
            body = await resp.aread()
            err_text = body.decode(errors="replace")[:500]
            logger.error(f"OpenRouter HTTP {resp.status_code}: {err_text}")
            raise LLMError(f"HTTP {resp.status_code}: {err_text}")

        # Pidetään kirjaa streamaavista tool_calls -paloista per index
        accumulated_tools: dict[int, dict] = {}

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

            # Handle streaming tool calls deltas
            tool_calls = delta.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    idx = tc.get("index", 0)
                    if idx not in accumulated_tools:
                        accumulated_tools[idx] = {
                            "id": tc.get("id", f"call_{idx}"),
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name", "") or "",
                                "arguments": ""
                            }
                        }
                    else:
                        if tc.get("id"):
                            accumulated_tools[idx]["id"] = tc["id"]
                    
                    fn_chunk = tc.get("function", {})
                    fn_name_chunk = fn_chunk.get("name")
                    if fn_name_chunk:
                        # Jos nimeä ei vielä asetettu tai kyseessä on uusi pala
                        if not accumulated_tools[idx]["function"]["name"]:
                            accumulated_tools[idx]["function"]["name"] = fn_name_chunk
                        elif accumulated_tools[idx]["function"]["name"] != fn_name_chunk:
                            # Vain jos uusi pala jatkaa nimeä
                            if not fn_name_chunk.startswith(accumulated_tools[idx]["function"]["name"]):
                                accumulated_tools[idx]["function"]["name"] += fn_name_chunk
                    
                    if fn_chunk.get("arguments"):
                        accumulated_tools[idx]["function"]["arguments"] += fn_chunk["arguments"]

        # Kun stream on päättynyt, lähetetään kootut eheät työkalukutsut
        if accumulated_tools:
            complete_tool_calls = [accumulated_tools[i] for i in sorted(accumulated_tools.keys())]
            logger.info(f"Koottu {len(complete_tool_calls)} työkalukutsua: {complete_tool_calls}")
            yield {"type": "tool_calls_complete", "tool_calls": complete_tool_calls}
