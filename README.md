# AI-suunnittelupaja (AI Design Studio)

Työtila, jossa suunnittelet uutta järjestelmää **yhdessä usean tekoälymallin ja agenttiroolin kanssa**. Sinä ohjaat keskustelua: agentit vastaavat vuorotellen omilla rooleillaan ja näkevät toistensa vastaukset (paneelikeskustelu), ja elävä suunnitteludokumentti kootaan ja päivitetään automaattisesti taustalla keskustelun pohjalta.

Kaikki mallit kulkevat yhden **OpenRouter**-avaimen kautta, joten voit sekoittaa eri tarjoajia (Claude, GPT, Gemini, Llama, DeepSeek, Qwen) ilman useaa tiliä.

---

## Ominaisuudet

- **Työkalujen Suoritus (Tool Calling / Code Execution)**: Agenteilla (kuten Kolli ja Matti) on mahdollisuus suorittaa Python-koodia suoraan palvelimella (`execute_python`) matemaattisten kaavojen, algoritmien tai skriptien validoimiseksi.
- **Aiheiden Hallinta & Tallennus (`data/topics/`)**: Keskustelut, dokumenttiluonnokset ja token-tilastot tallentuvat automaattisesti aihekohtaisesti. Voit luoda uusia aiheita, nimetä niitä ja vaihtaa vanhojen aiheiden välillä suoraan käyttöliittymästä.
- **Täsmäkutsu (@mention)**: Voit kutsua asiantuntijoita suoraan nimellä (esim. `@kolli`, `@matti`, `@aki`), jolloin vain mainitut agentit vastaavat ja turha automaattinen kehä vältetään.
- **Dynaamiset Agentit & Roolit**: Agenttien roolit, mallit ja järjestelmäkehotteet määritellään tiedostossa [`agents.json`](agents.json). Uusien agenttien lisäys onnistuu suoraan JSONia muokkaamalla.
- **Tuki Ilmaisille Malleille (`:free`)**: Oletuskonfiguraatio käyttää OpenRouterin ilmaisia huippumalleja (Llama 3.3 70B, DeepSeek R1, Gemini Flash Thinking, Qwen 2.5 Coder jne.).
- **Liukuva Ikkuna (Sliding Window)**: `conversation_for_model` rajaa historian vain viimeisiin aktiivisiin viesteihin, estäen token-kontekstin ja kustannusten hallitsemattoman kasvun.
- **Automaattinen Dokumenttipäivitys**: Kierroksen päätyttyä editori-malli päivittää markdown-suunnitelman automaattisesti taustalla ja striimaa sen käyttöliittymään (`doc_auto_update`).
- **Reaaliaikainen Token- ja Hintalaskuri**: UI laskee reaaliajassa toteutuneet prompt- ja completion-tokenit sekä arvioidut kustannukset mallikohtaisten hintatietojen pohjalta.

---

## Työnkulku

1. **Valitse Panelistit** — Klikkaa haluamasi asiantuntijat aktiivisiksi yläpalkista (esim. Seppo, Matti, Aki, Kolli, Legal).
2. **Keskustele** — Kirjoita ideasi; valitut asiantuntijat vastaavat vuorotellen omasta näkökulmastaan.
3. **Automaattinen Dokumentointi** — Editori päivittää suunnitelman markdown-muotoon oikeaan paneeliin.
4. **Tallenna** — Voit kopioida tai tallentaa valmiin dokumentin `documents/`-kansioon yhdellä klikkauksella.

---

## Asennus & Käynnistys (Windows / `py`)

```powershell
# 1. Asenna riippuvuudet
py -3 -m pip install -r requirements.txt

# 2. Aseta API-avain .env-tiedostoon
cp .env.example .env   # ja syötä OPENROUTER_API_KEY
```

Hanki API-avain: https://openrouter.ai/keys

### Käynnistys

```powershell
# Vaihtoehto A:
py -3 -m uvicorn main:app --reload --port 8002

# Vaihtoehto B:
py -3 main.py
```

Avaa selaimessa: **http://localhost:8002**

---

## Rakenne

| Tiedosto | Vastuu |
|---|---|
| `main.py` | FastAPI-backend, streamaavat SSE-päätepisteet (`/api/respond`, `/api/document`), automaattinen päivitys ja tallennus |
| `config.py` | Dynaamisen konfiguraation latauslogiikka ja oletusarvot |
| `agents.json` | Agenttien roolit, `system_prompt`-kehotteet, OpenRouter-mallit ja hinnoittelut |
| `llm.py` | OpenRouter SSE-streamaus ja token-käytön (usage) sieppaus |
| `static/index.html` | Käyttöliittymä: agenttivalitsin, chat, token/hintalaskuri ja markdown-dokumenttipaneeli |
| `.agents/AGENTS.md` | Agenttien säännöt, Windows `py`-ajotavat ja koodausohjeet |

