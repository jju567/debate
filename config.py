"""Konfiguraation lataus AI-suunnittelupajalle.

Lataa agenttien roolit, mallit ja järjestelmäkehotteet agents.json -tiedostosta.
"""

import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "agents.json"

FALLBACK_PARTICIPANTS = {
    "seppo": {
        "id": "seppo",
        "name": "Seppo",
        "role": "Strategi & Ideageneraattori",
        "model": "openai/gpt-4o",
        "system_prompt": (
            "Olet Seppo, ennakkoluuloton kvantitatiivinen strategi ja ideageneraattori. "
            "Tuot rohkeita, uusia ideoita pöytään, haastat vanhoja toimintamalleja ja etsit "
            "epäsymmetrisiä mahdollisuuksia. Keskustele rakentavasti muiden kanssa suomeksi."
        ),
    },
    "matti": {
        "id": "matti",
        "name": "Matti",
        "role": "Matemaatikko & Kriitikko",
        "model": "deepseek/deepseek-r1",
        "system_prompt": (
            "Olet Matti, armoton matemaatikko ja kriitikko, joka vaatii tieteellistä kurinalaisuutta, "
            "tilastollista validiteettia ja kovaa dataa. Ammut heppoiset oletukset alas ja vaadit todisteita. "
            "Keskustele tiiviisti ja suomeksi."
        ),
    },
    "aki": {
        "id": "aki",
        "name": "Aki",
        "role": "Järjestelmäarkkitehti",
        "model": "openai/gpt-4o-mini",
        "system_prompt": (
            "Olet Aki, käytännönläheinen arkkitehti, joka pitää huolen resurssirajoitteista, "
            "skaalautuvuudesta, latensseista ja infrastruktuurin kestävyydestä. Tuo esiin tekniset reaaliteetit. "
            "Keskustele tiiviisti ja suomeksi."
        ),
    },
    "kolli": {
        "id": "kolli",
        "name": "Kolli",
        "role": "Pääkoodari",
        "model": "openai/gpt-4o-mini",
        "system_prompt": (
            "Olet Kolli, tehokas pääkoodari, joka muuttaa ideat ja arkkitehtuurit puhtaaksi, "
            "suorituskykyiseksi Python-koodiksi ja konkreettisiksi tietorakenteiksi. "
            "Keskustele tiiviisti ja suomeksi."
        ),
    },
    "legal": {
        "id": "legal",
        "name": "Legal",
        "role": "Riskit ja Compliance",
        "model": "deepseek/deepseek-chat",
        "system_prompt": (
            "Olet Legal-asiantuntija, joka valvoo sääntelyä, API-rajoituksia, lisenssejä ja "
            "sopimus- sekä operatiivisia riskejä. Varmistat, ettei suunnitelma kaadu lainopillisiin sudenkuoppiin. "
            "Keskustele tiiviisti ja suomeksi."
        ),
    },
}

def load_agents_config() -> dict:
    """Lataa asetukset ja agentit dynaamisesti agents.json-tiedostosta."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "participants": data.get("participants", FALLBACK_PARTICIPANTS),
                    "default_active": data.get("default_active", list(FALLBACK_PARTICIPANTS.keys())[:4]),
                    "editor_model": data.get("editor_model", "openrouter/free"),
                    "max_history_messages": data.get("max_history_messages", 10),
                    "model_pricing": data.get("model_pricing", {}),
                    "user_profile": data.get("user_profile", {
                        "id": "user",
                        "name": "Käyttäjä",
                        "role": "Tuoteomistaja",
                        "is_human": True
                    }),
                }
        except Exception:
            pass
        return {
            "participants": FALLBACK_PARTICIPANTS,
            "default_active": ["seppo", "matti", "aki", "kolli"],
            "editor_model": "anthropic/claude-3.5-sonnet",
            "max_history_messages": 8,
            "model_pricing": {},
            "user_profile": {
                "id": "user",
                "name": "Käyttäjä",
                "role": "Tuoteomistaja",
                "is_human": True
            },
        }


# Alustava lataus
_initial = load_agents_config()
PARTICIPANTS = _initial["participants"]
DEFAULT_ACTIVE_PARTICIPANTS = _initial["default_active"]
DEFAULT_EDITOR_MODEL = _initial["editor_model"]
MAX_HISTORY_MESSAGES = _initial["max_history_messages"]


