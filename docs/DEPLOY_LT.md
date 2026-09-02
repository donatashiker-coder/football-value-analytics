# Kaip paleisti programą internete (nemokamai, ~15 min.)

Reikės trijų nemokamų paskyrų. Visos registruojasi per naršyklę, kortelės nereikia.

## 1. Duomenų bazė — Neon
1. Eik į https://neon.tech ir prisijunk (galima su GitHub ar Google).
2. Sukurk projektą (pavadinimas bet koks, regionas *Europe / Frankfurt*).
3. Skiltyje **Connect** nukopijuok connection string. Jis atrodo taip:
   `postgresql://neondb_owner:xxxx@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`

## 2. Duomenų raktai
- **football-data.org** (rungtynės, rezultatai): https://www.football-data.org/client/register — raktas ateina el. paštu.
- **The Odds API** (koeficientai, 500 kreditų/mėn.): https://the-odds-api.com — raktas rodomas po registracijos.

## 3. Hostingas — Render
1. Eik į https://dashboard.render.com ir prisijunk su GitHub.
2. Atidaryk šią nuorodą:
   https://render.com/deploy?repo=https://github.com/donatashiker-coder/football-value-analytics
3. Render paprašys trijų reikšmių:
   - `DATABASE_URL` — connection string iš Neon (1 žingsnis)
   - `FOOTBALL_DATA_API_KEY` — iš football-data.org
   - `ODDS_API_KEY` — iš The Odds API
4. Spausk **Apply / Deploy**. Pirmas build trunka ~5–8 min. Adresas bus
   `https://football-value-analytics-xxxx.onrender.com`.

## 4. Pirmas duomenų užkrovimas
Atsidaryk programą, skiltyje **Dashboard** paspausk mygtuką, kuris paleidžia pilną duomenų atnaujinimą
(„pipeline“). Tai užtrunka kelias minutes: parsiunčia rungtynes, statistiką, koeficientus ir suskaičiuoja modelius.

## Ką verta žinoti
- Nemokamas Render servisas užmiega po 15 min. be lankytojų. Pirmas atidarymas tada trunka ~30–60 s.
- Kasdieniai atnaujinimai vyksta 06:00–07:05 Londono laiku. Kad servisas tuo metu būtų pabudęs,
  repo savininkas turi nustatyti GitHub kintamąjį `APP_URL` su tavo Render adresu — atsiųsk jam adresą.
- Programa neturi prisijungimo: kas žino adresą, tas ją mato. Nesidalink adresu viešai.
- Koeficientų kreditai: 500/mėn. Programa atnaujina koeficientus kas 12 val., to užtenka.
