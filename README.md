# PortalPath

College football transfer portal analysis tool. Uses historical transfer data (2021–2025) to score and rank which programs best develop players surfaced through an interactive dashboard.

**Live Website:** [portalpath.onrender.com](https://portalpath.onrender.com)

**Team 90** — Matty Maloni, Toni Comer, Shawn Chen

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Running the project

### Option A — use the included data (no API key needed)
Pre-built portal index files for 2021–2026 are included in `data/processed/`. Just launch the dashboard:
```bash
python run.py --dashboard
# Open http://localhost:8051
```

### Option B — pull your own data and regenerate
Requires a free CFBD API key from [collegefootballdata.com/key](https://collegefootballdata.com/key). Create a `.env` file:
```
CFBD_API_KEY=your_key_here
```
Then run the full pipeline:
```bash
python run.py
```

### Individual steps
```bash
python run.py --fetch      # pull raw data from CFBD API       - data/raw/
python run.py --clean      # clean raw data                    - data/processed/
python run.py --features   # compute composite scores + deltas - data/processed/
python run.py --rank       # build portal index                - data/processed/
python run.py --algorithm1 # compile + run Transfer Flow Score - data/processed/
python run.py --dashboard  # launch interactive dashboard at http://localhost:8051
```

---

## Project structure

```
run.py                            # pipeline orchestrator (start here)
pipeline/
    fetch.py                      # CFBD API ingestion
    clean.py                      # data cleaning + name normalization
    features.py                   # composite scores + success delta + success factor
    rank.py                       # PageRank + development score -> portal index
data/
    raw/                          # raw API dumps (gitignored)
    processed/                    # derived outputs (gitignored)
viz/
    dashboard.py                  # Dash app
    bokeh_charts.py               # chart components
    logos/                        # FBS team logos
algorithm1.cpp                    # Transfer Flow Score (C++)
```

---

## Data pipeline

```
fetch.py   ->  data/raw/transfers.csv, player_stats.csv, recruits.csv,
               ppa.csv, usage.csv, sp_ratings.csv

clean.py   ->  data/processed/stats_clean.csv
               data/processed/transfers_clean.csv

features.py ->  success_delta (pre/post composite score difference per transfer)
               success_factor (signal reliability: Tier 1 played, Tier 2 possible injury, Tier 3 never played)
               -> data/processed/scored_transfers.csv

rank.py    ->  portal_index = 0.3 * PageRank + 0.7 * dev_score
               -> data/processed/portal_index_{year}.csv
               -> data/processed/portal_index_alltime.csv

algorithm1.cpp ->  transfer flow score per school
                   -> data/processed/algorithm1_rankings_{year}.csv
                   -> data/processed/algorithm1_rankings_alltime.csv
```

**Composite score formula** varies by position group. Offensive skill players weight PPA (0.35–0.40) and usage (0.20–0.25) highest, with position-specific volume stats (yards, TDs, efficiency multipliers). Defenders use PPA + havoc (tackles, sacks, TFL, hurries) + coverage. Kickers and punters use their own formulas.

**Success delta** = `post_score - pre_score` for each transfer, using the composite scores from the season before and after the move.

**Success factor** = reliability weight (0–1) on each transfer row. Tier 1 players (met volume thresholds) weighted by pre-score magnitude. Tier 2 (possible injury year) and Tier 3 (never played) get lower base weights, boosted slightly by recruiting stars.

**Portal index** = `0.3 * PageRank + 0.7 * dev_score_norm`. PageRank captures a school's centrality in the transfer network (prestige diffusion weighted by player pre-scores). Dev score measures whether incoming transfers actually produce post-transfer, adjusted for position importance and weighted by success factor.

Data source: [CollegeFootballData.com](https://collegefootballdata.com) (free public API, 2021–2025)

---

## Algorithms

### Current: PageRank + Development Score
The portal index combines two signals:
- **PageRank** — iterative prestige diffusion on the transfer graph. Edge weights = `avg(pre_score) * log(1 + transfer_count)`. Captures which schools are hubs for high-quality incoming talent.
- **Development Score** — success-factor-weighted average post-score per destination school, percentile-ranked within position and adjusted by position importance weight (QB=1.4, P=0.45). Captures whether players actually improve after transferring there.

### Transfer Flow Score (algorithm1.cpp)
A C++ algorithm. Scores each school based on how much incoming transfers improve after arriving vs. how much outgoing transfers improve after leaving. Penalizes programs where players consistently improve only after leaving (evidence of being held back). Weighted by success factor and conference strength.

Formula: `0.5 * incoming_score - 0.3 * outgoing_score + 0.2 * net_ratio`

The dashboard shows all three rankings side by side and an agreement scatter at the bottom, where the two algorithms agree there's high confidence, where they diverge is worth looking into.
