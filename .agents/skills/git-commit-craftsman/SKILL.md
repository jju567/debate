---
name: git-commit-craftsman
description: >-
  Käytä tätä skilliä aina kun luodaan, ehdotetaan tai muotoillaan Git-commit-viestejä
  ja -kuvauksia. Muotoilee täsmälliset, informatiiviset ja konventionaaliset (Conventional Commits)
  commit-viestit ilman geneeristä jargonia.
---

# Git Commit Craftsman Skill

Tämä skilli ohjaa huippuluokan, informatiivisten ja selkeiden Git-commit-viestien luomista.
Unohda geneeriset viestit kuten *"fix bug"*, *"update code"* tai *"add features"*.

---

## 1. Commit-viestin Rakenne (Tiivis Max 3 Riviä)

Oletusformaatti on tiivis ja ytimekäs (maksimissaan 3 riviä):

```text
<type>(<scope>): <kuvaava otsikko>

- <tiivis päämuutos 1>
- <tiivis päämuutos 2>
```

---

## 2. Tyypit (`<type>`)

Valitse täsmällinen tyyppi:
- `feat`: Uusi toiminnallisuus, piirre tai moduuli (esim. uusi agentti, laskuri, SSE-tapahtuma).
- `fix`: Bugikorjaus, laskentavirheen korjaus tai poikkeustilanteen esto.
- `refactor`: Koodin uudelleenjärjestely (esim. moduulijako alle 500 riviin) ilman toimintalogiikan muutosta.
- `perf`: Suorituskykyparannus (latenssi, token-kulutuksen optimointi, sliding window).
- `test`: Yksikkötestit.
- `docs`: README.md- tai koodidokumentaation päivitys.
- `chore`: Konfiguraatiot, mallipäivitykset, paketointi.

---

## 3. Sovellusalueet (`<scope>`) tässä projektissa

Käytä projektin komponentteja skooppina:
- `agents`: Agenttien määritykset, `agents.json`, persoonat ja kehotteet.
- `llm`: OpenRouter-kutsu, streaming, SSE ja token-seuranta.
- `ui`: Frontend, `static/index.html`, laskurit ja komponentit.
- `config`: Asetusten lataus, liukuva ikkuna ja hinnoittelut.
- `doc`: Suunnitteludokumentin luonti ja automaattipäivitys.

---

## 4. Hyvän Commit-viestin Säännöt

1. **Otsikko (Header)**:
   - Max 72 merkkiä.
   - Pienellä alkukirjaimella kaksoispisteen jälkeen.
   - Ei pistettä loppuun.
   - Kerro *mitä* ja *missä*.
2. **Leipäteksti (Body)**:
   - Selitä **miksi** muutos tehtiin.
   - Selitä **mitä** teknisesti muuttui.
   - Tiivis ranskalaisin viivoin.
