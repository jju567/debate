"""Älykäs mallireititin ja automaattinen mallinvalinta (Model Router).

Valitsee optimaalisen tekoälymallin tehtävän ja roolin mukaan
sekä huolehtii automaattisesta varamallista (fallback), jos saldot tai rajat paukkuvat (HTTP 402).
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger("debate.model_router")
logger.setLevel(logging.INFO)

# Roolikohtaiset ilmaiset varamallit (Fallback / Backup) kun maksullinen malli antaa virheen (402, 429, jne.)
ROLE_FALLBACK_MODELS = {
    "kolli": "cohere/north-mini-code:free",
    "matti": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "aki": "nvidia/nemotron-3-super-120b-a12b:free",
    "seppo": "minimax/minimax-m3:free",
    "legal": "nvidia/nemotron-3-super-120b-a12b:free",
    "editor": "openrouter/free",
}

DEFAULT_FREE_FALLBACK = "openrouter/free"
FREE_FALLBACK_MODEL = "openrouter/free"


def get_fallback_model(participant_id: str) -> str:
    """Palauttaa agentin rooliin täsmällisesti sopivan ilmaisen varamallin."""
    return ROLE_FALLBACK_MODELS.get(participant_id, DEFAULT_FREE_FALLBACK)

# Oletusarvoiset kevyet ja raskaat maksulliset mallit rooleittain
ROLE_MODELS = {
    "kolli": {
        "light": "openai/gpt-4o-mini",
        "heavy": "anthropic/claude-3.5-sonnet",
    },
    "matti": {
        "light": "deepseek/deepseek-chat",
        "heavy": "deepseek/deepseek-r1",
    },
    "aki": {
        "light": "openai/gpt-4o-mini",
        "heavy": "anthropic/claude-3.5-sonnet",
    },
    "seppo": {
        "light": "openai/gpt-4o-mini",
        "heavy": "openai/gpt-4o",
    },
    "legal": {
        "light": "deepseek/deepseek-chat",
        "heavy": "anthropic/claude-3.5-sonnet",
    },
    "editor": {
        "light": "openai/gpt-4o-mini",
        "heavy": "anthropic/claude-3.5-sonnet",
    },
}

DEFAULT_LIGHT_MODEL = "openai/gpt-4o-mini"
DEFAULT_HEAVY_MODEL = "anthropic/claude-3.5-sonnet"


def is_heavy_task(messages: list[dict], participant_id: str = "") -> bool:
    """Tunnistaa viestihistorian ja käyttäjän pyynnön perusteella, tarvitaanko raskasta mallia."""
    if not messages:
        return False
    
    # Tarkistetaan viimeisimmät viestit (erityisesti käyttäjän pyyntö)
    recent_texts = []
    for m in messages[-3:]:
        c = m.get("content")
        if isinstance(c, str):
            recent_texts.append(c.lower())
    
    full_text = " ".join(recent_texts)
    
    # 1. Koodiblokit viestissä
    if "```python" in full_text or "```sql" in full_text:
        return True
        
    # 2. Avainsanat
    for kw in HEAVY_KEYWORDS:
        if kw in full_text:
            return True
            
    # 3. Koodarin ja matemaatikon pitkät suoritukset
    if participant_id in ["kolli", "matti"] and len(full_text) > 400:
        return True
        
    return False


def resolve_model(
    configured_model: str,
    participant_id: str,
    messages: list[dict] | None = None,
    force_tier: str | None = None
) -> str:
    """Määrittää suoritettavan mallin.
    
    Jos configured_model on 'auto' tai 'auto_tier':
      - arvioi onko tehtävä raskas vai kevyt ja valitsee sopivan mallin.
    Muussa tapauksessa palauttaa suoraan määritetyn mallin.
    """
    if not configured_model or configured_model.lower() in ["auto", "auto_tier", "dynamic"]:
        role_info = ROLE_MODELS.get(participant_id, {})
        light_model = role_info.get("light", DEFAULT_LIGHT_MODEL)
        heavy_model = role_info.get("heavy", DEFAULT_HEAVY_MODEL)
        
        if force_tier == "heavy":
            return heavy_model
        elif force_tier == "light":
            return light_model
            
        if messages and is_heavy_task(messages, participant_id):
            logger.info(f"Auto-Router: Valittu raskas malli ({heavy_model}) osallistujalle {participant_id}")
            return heavy_model
        else:
            logger.info(f"Auto-Router: Valittu kevyt malli ({light_model}) osallistujalle {participant_id}")
            return light_model
            
    return configured_model
