# Agent Rules & Execution Instructions

## Tiedostojen Koko & Refaktorointi
- **AINA** kun kooditiedosto (esim. Python-ohjelmatiedosto) kasvaa yli **500 rivin**, se on refaktoroitava useampaan pienempään ja selkeämpään tiedostoon (yhden vastuun periaate / moduulijako).

## Python Suoritus & Testaus (Windows)
- **AINA** käytetään komentoa **`py`** Python-skriptien suorittamiseen (esim. `py main.py`, `py -m uvicorn main:app`). Komento `python` tai `pytest` ei ole suoraan PATH-muuttujassa tässä ympäristössä.
- Yksikkötestien ajamiseen käytetään:
  - Yksittäinen testi: `py -m unittest tests/test_<nimi>.py`
  - Koko testisetti: `py -m unittest discover tests`

## README.md - Automaattinen Dokumentointi
- **AINA** kun agentti toteuttaa uuden ominaisuuden, moduulin tai merkittävän muutoksen, se **dokumentoidaan välittömästi** projektin [`README.md`](README.md):ään toteutuksen jälkeen.
- Dokumentointi tehdään oikeaan paikkaan README:n rakenteessa (esim. "Ominaisuudet", "Arkkitehtuuri" tai "Konfigurointi"-osiot). Jos sopivaa osiota ei löydy, se **luodaan**.
- Dokumentoinnin minimivaatimukset kullekin uudelle ominaisuudelle:
  - **Nimi ja lyhyt kuvaus** (1-2 lausetta: mitä tekee ja miksi)
  - **Tiedostopolku** tai moduulinimi (esim. `config.py`, `agents.json`)
  - **Konfiguraatio** - listataan oleelliset `.env`-muuttujat tai config-parametrit (jos on)
  - **Käyttö / integraatiotapa** - miten ominaisuus kytketään käyttöön
- Älä kirjoita liian pitkiä selityksiä - README pysyy tiiviinä ja luettavana. Käytä bullet-listoja, koodiesimerkkejä ja taulukoita tarvittaessa.
- **Poikkeus**: Pienet refaktoroinnit, bugikorjaukset tai testien lisäykset (jotka eivät muuta julkista käyttäytymistä) **eivät** vaadi README-päivitystä.

## Git Commit -Viestit (Automaattinen Ehdotus Skillin Mukaisesti)
- **AINA** kun agentti saa valmiiksi uuden ominaisuuden (feature), bugin korjauksen (fix) tai refaktoroinnin, agentti käyttää [`git-commit-craftsman`](skills/git-commit-craftsman/SKILL.md) -skilliä ja **tarjoaa vastauksen lopussa valmiin tiiviin Git-commit-viestin (max 3 riviä)** muodossa:
  ```text
  <type>(<scope>): <kuvaava otsikko>

  - <tiivis päämuutos 1>
  - <tiivis päämuutos 2>
  ```
