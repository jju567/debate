# AI-suunnittelupaja (AI Design Studio)

Työtila, jossa suunnittelet uutta järjestelmää **yhdessä usean tekoälymallin ja agenttiroolin kanssa**. Sinä ohjaat keskustelua: agentit vastaavat vuorotellen omilla rooleillaan ja näkevät toistensa vastaukset (paneelikeskustelu), ja elävä suunnitteludokumentti kootaan ja päivitetään automaattisesti taustalla keskustelun pohjalta.

Kaikki mallit kulkevat yhden **OpenRouter**-avaimen kautta, joten voit sekoittaa eri tarjoajia (Claude, GPT, Gemini, Llama, DeepSeek, Qwen) ilman useaa tiliä.

---

## Ominaisuudet

- **Agenttikohtaiset Ilmaiset Varamallit (Backup / Fallback)**: Jos ostettu tai määritetty malli antaa virheen (kuten saldo loppu HTTP 402, tai limiitti HTTP 429), järjestelmä siirtyy automaattisesti roolikohtaisesti parhaaseen **ilmaiseen** varamalliin:
  - **Kolli** (Koodaus) ➔ `cohere/north-mini-code:free`
  - **Matti** (Matematiikka & Logiikka) ➔ `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
  - **Aki** & **Legal** (Arkkitehtuuri & Sääntely) ➔ `nvidia/nemotron-3-super-120b-a12b:free`
  - **Seppo** (Strategia & Ideointi) ➔ `minimax/minimax-m3:free`
  - **Editori** (Dokumentin kokoaminen) ➔ `openrouter/free`
- **Dokumenttikirjasto & Paikalliset Viitteet**: Voit viitata sekä ladattuihin viitetiedostoihin (`data/library/`) että tietokoneella jo oleviin kansioihin ja tiedostoihin. Tiedostot eivät paisuta kontekstia pysyvästi, vaan agentit lukevat niitä tarpeen mukaan.
- **Asynkroninen Taustalaskenta & Työjono (`background_jobs.py`)**: Raskaat simulaatiot, monimutkaiset data-ajot ja pitkäkestoiset Python-skriptit suoritetaan omassa taustaprosessissaan ilman HTTP/SSE-aikakatkaisurajoituksia (`start_background_job`, `check_job_status`, `list_background_jobs`).
- **Työkalujen Suoritus (Tool Calling, REPL, Verkkohaku, Tiedoston Luonti & Luku)**: Agenteilla on monipuolinen työkalupakki:
  - `write_local_file`: Luo tai tallentaa koodit, skriptit ja tiedostot suoraan levylle (esim. `work/skripti.py` tai `scripts/...`).
  - `start_background_job` & `check_job_status`: Asynkroninen raskas taustalaskenta ilman aikarajoja (Polars, laaja data, simulaatiot).
  - `read_local_file`: Lukee koneella olemassa olevan paikallisen tiedoston sisällön (esim. `work/polars2.py`).
  - `list_local_directory`: Listaa paikallisen kansion tiedostorakenteen katsausta varten.
  - `read_library_doc` & `list_library_docs`: Lukee käyttäjän lataamia kirjastodokumentteja.
  - `web_search`: Etsii ajantasaista tietoa ja teknologiavertailuja verkosta (DuckDuckGo).
  - `fetch_webpage`: Lukee ja siistii annettujen verkkosivujen ja dokumentaatioiden sisällön.
  - `eval_python_expression`: Salamannopea in-memory Python REPL kevyisiin laskelmiin.
  - `execute_python`: Eristetty nopea Python-skriptien pikatestaus (`py -3`, < 15s).
- **Aiheiden Hallinta & Tallennus (`data/topics/`)**: Keskustelut, dokumenttiluonnokset ja token-tilastot tallentuvat automaattisesti aihekohtaisesti. Voit luoda uusia aiheita, nimetä niitä ja vaihtaa vanhojen aiheiden välillä suoraan käyttöliittymästä.
- **Täsmäkutsu (@mention)**: Voit kutsua asiantuntijoita suoraan nimellä (esim. `@kolli`, `@matti`, `@aki`), jolloin vain mainitut agentit vastaavat ja turha automaattinen kehä vältetään.
- **Dynaamiset Agentit & Roolit**: Agenttien roolit, mallit ja järjestelmäkehotteet määritellään tiedostossa [`agents.json`](agents.json). Uusien agenttien lisäys onnistuu suoraan JSONia muokkaamalla.
- **Tuki Ilmaisille Malleille (`:free`)**: Oletuskonfiguraatio käyttää OpenRouterin ilmaisia huippumalleja (Llama 3.3 70B, DeepSeek R1, Gemini Flash Thinking, Qwen 2.5 Coder jne.).
- **Liukuva Ikkuna (Sliding Window)**: `conversation_for_model` rajaa historian vain viimeisiin aktiivisiin viesteihin, estäen token-kontekstin ja kustannusten hallitsemattoman kasvun.
- **Automaattinen Dokumenttipäivitys**: Kierroksen päätyttyä editori-malli päivittää markdown-suunnitelman automaattisesti taustalla ja striimaa sen käyttöliittymään (`doc_auto_update`).
- **HAR-RV Volatiliteettimalli & Rekiimianalyysi (`work/regime_analysis.py`)**: Estimoi OLS-regressiolla Heterogeneous Autoregressive Realized Volatility -mallin parametrit ($\alpha, \beta_d, \beta_w, \beta_m$) 3v 5min datasta ($R^2 = 99.89\%$) ja luokittelee markkinatilan (HIGH_VOL, NORMAL, LOW_VOL).
- **3v 5min Sharpe-simulaatio (`work/sharpe_simulation_3y.py`)**: Simuloi mean-reversion volatiliteetti-iskustrategiaa 306 578 kynttilällä (2023–2026). Vertaa bruttotuottoa (Gross Sharpe: +1.725) ja kuluilla painotettua nettotuottoa Maker 0.15% (-39.56) sekä Taker 0.25% (-50.98) kuluilla.
- **Binance 5min Klines Historiadatalataaja (`binance_5min_loader.py`)**: Raskaan volatiliteetti- ja mikrostruktuuritutkimuksen (HAR-RV, Sharpe) datalataaja, joka hakee 2–3 vuoden (2023-08-01 -> 2026-08-31) 5min kynttilähistorian (`BTCUSDT`) Binance REST API:sta rate limit -suojattuna ja tallentaa sen päivittäin partitionoituihin Parquet-tiedostoihin (`data/binance_5min/`). Datasetin laatu ja eheys validoidaan skriptillä `scripts/clean_and_verify_dataset.py`.
- **Reaaliaikainen Token- ja Hintalaskuri**: UI laskee reaaliajassa toteutuneet prompt- ja completion-tokenit sekä arvioidut kustannukset mallikohtaisten hintatietojen pohjalta.
- **Koodilohkojen Kopiointipainike (Copy to Clipboard)**: Kaikkiin chat-viestien ja suunnitteludokumentin koodilohkoihin (`<pre>`) luodaan dynaamisesti leikepöydälle kopioiva painike (`📋 Kopioi`), joka antaa visuaalisen vahvistuksen (`✅ Kopioitu!`).

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

| Tiedosto / Kansio | Vastuu |
|---|---|
| `main.py` | FastAPI-backend, streamaavat SSE-päätepisteet (`/api/respond`, `/api/document`), automaattinen päivitys ja tallennus |
| `schemas.py` | Pydantic-tietomallit ja pyyntörakenteet |
| `config.py` | Dynaamisen konfiguraation latauslogiikka ja oletusarvot |
| `agents.json` | Agenttien roolit, `system_prompt`-kehotteet, OpenRouter-mallit ja hinnoittelut |
| `llm.py` | OpenRouter SSE-streamaus ja token-käytön (usage) sieppaus |
| `tools.py` | Agenttien työkalut (Python-suoritus, REPL, verkkohaku, tiedostoluku jne.) |
| `tool_executor.py` | Työkalukutsujen suoritus, lokitus ja tulosten syöttö takaisin malleille (Agent Tool Loop) |
| `library.py` | Viitedokumenttikirjaston hallinta |
| `storage_routes.py` | Aiheiden (topics) ja kirjastotiedostojen REST-reitit |
| `static/index.html` | Käyttöliittymä: agenttivalitsin, chat, token/hintalaskuri ja markdown-dokumenttipaneeli |
| `work/` | Agenttien tuottamat Python-koodit, analyysiskriptit ja kehitystiedostot |
| `results/` | Laskenta-, simulaatio- ja analyysitulokset, raportit (JSON, CSV, TXT, kuvaajat) |
| `scripts/` | Apuskriptit, mallitarkistukset ja yhteyden testiskriptit |
| `tests/` | Automaattiset yksikkötestit (`py -m unittest discover tests`) |
| `data/` | Aihetallennukset (`data/topics/`) ja ladatut viitedokumentit (`data/library/`) |
| `.agents/AGENTS.md` | Agenttien säännöt, Windows `py`-ajotavat ja koodausohjeet |

