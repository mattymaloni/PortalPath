# PortalPath

College football transfer portal analysis tool. Uses historical transfer data to map which programs best develop players, visualized as an interactive network on a US map.

**Team 90** — Matty Maloni, Toni Comer, Shawn Chen

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your CFBD API key to .env (free at https://collegefootballdata.com/key)
```

---

## Running the project

### Just launch the map (fastest — uses included `edges.csv`)
```bash
python viz/map.py
# Open http://localhost:8050
```

### Full pipeline (fetch → clean → map)
```bash
python run.py
```

### Individual steps
```bash
python run.py --fetch    # pull raw data from CFBD API  → saves to data/raw/
python run.py --clean    # clean + compute edges        → saves to data/processed/
python run.py --map      # launch the interactive map
```

---

## Project structure

```
run.py                        # pipeline orchestrator (start here)
pipeline/
    fetch.py                  # API data ingestion
    clean.py                  # data cleaning + success delta computation
data/
    raw/                      # raw API dumps (gitignored)
    processed/
        edges.csv             # derived edge list (tracked in git)
        stats_clean.csv       # gitignored
        transfers_clean.csv   # gitignored
viz/
    map.py                    # interactive Dash map (main deliverable)
    coords.py                 # lat/lon for all FBS programs
```

---

## How the map works

- **Nodes** = FBS programs, sized by incoming transfer volume
- **Click a school** to reveal its transfer routes as colored arcs
- **Arc color** = success delta: green (players improved) → amber → red (declined)
- **Arc thickness** = transfer volume

---

## Data pipeline

```
pipeline/fetch.py  →  data/raw/transfers.csv, player_stats.csv, recruits.csv, ppa.csv, usage.csv
pipeline/clean.py  →  data/processed/stats_clean.csv, transfers_clean.csv, edges.csv
viz/map.py         reads data/processed/edges.csv
```

Success delta formula: `0.4×PPA + 0.3×usage + 0.2×yards/1000 + 0.1×havoc/10`

Data source: [CollegeFootballData.com](https://collegefootballdata.com) (free public API, 2021–2025)
