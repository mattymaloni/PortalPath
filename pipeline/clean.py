import math
import pandas as pd


# ── Step 1: Pivot stats from long to wide ─────────────────────────────────────
def build_stats_wide():
    """Pivot raw player stats from long format to one row per player-season."""
    print("Building stats wide...")
    df = pd.read_csv("data/raw/player_stats.csv")

    keep = {
        'rushing':       ['YDS', 'CAR', 'TD'],
        'receiving':     ['YDS', 'REC', 'TD'],
        'passing':       ['YDS', 'TD', 'ATT'],
        'defensive':     ['TOT', 'SOLO', 'SACKS', 'TFL', 'PD', 'QB HUR', 'TD'],
        'interceptions': ['INT', 'YDS', 'TD'],
    }
    mask = df.apply(
        lambda row: row['category'] in keep and row['stat_type'] in keep[row['category']], axis=1
    )
    df = df[mask].copy()
    df['col'] = df['category'] + '_' + df['stat_type']

    wide = df.pivot_table(
        index=['year', 'player_id', 'player', 'team'],
        columns='col',
        values='stat',
        aggfunc='first',
    ).reset_index()
    wide.columns.name = None

    wide['yards_per_carry'] = wide.get('rushing_YDS', 0) / wide.get('rushing_CAR', 1).replace(0, 1)
    wide['yards_per_rec']   = wide.get('receiving_YDS', 0) / wide.get('receiving_REC', 1).replace(0, 1)

    print(f"  Stats wide: {wide.shape}")
    return wide


# ── Step 2: Merge PPA and usage into stats ────────────────────────────────────
def merge_ppa_usage(wide):
    """Join PPA and usage onto the wide stats table by player+team+year."""
    print("Merging PPA and usage...")
    df_ppa   = pd.read_csv("data/raw/ppa.csv")
    df_usage = pd.read_csv("data/raw/usage.csv")

    for df in [wide, df_ppa, df_usage]:
        df['player_norm'] = df['player'].str.lower().str.strip()
        df['team_norm']   = df['team'].str.lower().str.strip()

    wide = wide.merge(
        df_ppa[['year', 'player_norm', 'team_norm', 'avg_ppa_total', 'avg_ppa_rushing', 'avg_ppa_passing']],
        on=['year', 'player_norm', 'team_norm'], how='left',
    )
    wide = wide.merge(
        df_usage[['year', 'player_norm', 'team_norm', 'usage_overall', 'usage_rush', 'usage_pass']],
        on=['year', 'player_norm', 'team_norm'], how='left',
    )

    wide.to_csv("data/processed/stats_clean.csv", index=False)
    print("  Saved data/processed/stats_clean.csv")
    return wide


# ── Step 3: Clean transfers ───────────────────────────────────────────────────
def clean_transfers():
    """Drop uncommitted portal entries and normalize names for joining."""
    print("Cleaning transfers...")
    df = pd.read_csv("data/raw/transfers.csv")
    df = df.dropna(subset=['destination'])
    df['player_norm']      = (df['first_name'] + ' ' + df['last_name']).str.lower().str.strip()
    df['origin_norm']      = df['origin'].str.lower().str.strip()
    df['destination_norm'] = df['destination'].str.lower().str.strip()
    print(f"  Transfers with destination: {len(df)}")
    return df


# ── Step 4: Join recruiting stars ─────────────────────────────────────────────
def join_recruits(df_transfers):
    """Attach recruiting star rating to each transfer row."""
    print("Joining recruiting data...")
    df_recruits = pd.read_csv("data/raw/recruits.csv")
    df_recruits['player_norm'] = df_recruits['name'].str.lower().str.strip()
    df_recruits_dedup = (
        df_recruits.sort_values('rating', ascending=False)
        .drop_duplicates(subset='player_norm')
    )
    df_transfers = df_transfers.merge(
        df_recruits_dedup[['player_norm', 'stars', 'rating']].rename(
            columns={'stars': 'recruit_stars', 'rating': 'recruit_rating'}
        ),
        on='player_norm', how='left',
    )
    return df_transfers


# ── Step 5: Attach pre/post stats ─────────────────────────────────────────────
def attach_pre_post_stats(df_transfers, stats_wide):
    """Join the season before and after each transfer onto the transfer row."""
    print("Attaching pre/post stats...")
    cols = ['year', 'player_norm', 'team_norm',
            'avg_ppa_total', 'usage_overall',
            'rushing_YDS', 'receiving_YDS', 'passing_YDS',
            'yards_per_carry', 'yards_per_rec',
            'defensive_TOT', 'defensive_SACKS', 'defensive_TFL',
            'defensive_PD', 'interceptions_INT']
    stats_key = stats_wide[[c for c in cols if c in stats_wide.columns]].copy()

    pre = stats_key.copy()
    pre.columns = [
        'pre_year' if c == 'year'
        else c if c in ('player_norm', 'team_norm')
        else 'pre_' + c
        for c in pre.columns
    ]
    pre['year'] = pre['pre_year'] + 1
    pre = pre.rename(columns={'team_norm': 'origin_norm'})

    post = stats_key.copy()
    post.columns = [
        'post_year' if c == 'year'
        else c if c in ('player_norm', 'team_norm')
        else 'post_' + c
        for c in post.columns
    ]
    post['year'] = post['post_year'] - 1
    post = post.rename(columns={'team_norm': 'destination_norm'})

    df_transfers = df_transfers.merge(pre,  on=['year', 'player_norm', 'origin_norm'],      how='left')
    df_transfers = df_transfers.merge(post, on=['year', 'player_norm', 'destination_norm'], how='left')
    return df_transfers


# ── Step 6: Compute success delta ─────────────────────────────────────────────
def _n(val):
    try:
        return 0 if (val is None or math.isnan(float(val))) else float(val)
    except (TypeError, ValueError):
        return 0

def composite_score(ppa, usage, rush_yds, rec_yds, pass_yds,
                    def_tot, def_sacks, def_tfl, def_pd, ints):
    total_yds = _n(rush_yds) + _n(rec_yds) + _n(pass_yds)
    havoc = _n(def_tot) + (_n(def_sacks) * 2) + (_n(def_tfl) * 1.5) + _n(def_pd) + (_n(ints) * 3)
    return (0.4 * _n(ppa)) + (0.3 * _n(usage)) + (0.2 * (total_yds / 1000)) + (0.1 * (havoc / 10))

def compute_success_delta(df_transfers):
    """Compute pre/post composite scores and their delta for each transfer."""
    print("Computing success delta...")

    def score_row(prefix, r):
        return composite_score(
            r.get(f'{prefix}avg_ppa_total'),   r.get(f'{prefix}usage_overall'),
            r.get(f'{prefix}rushing_YDS'),      r.get(f'{prefix}receiving_YDS'),
            r.get(f'{prefix}passing_YDS'),      r.get(f'{prefix}defensive_TOT'),
            r.get(f'{prefix}defensive_SACKS'),  r.get(f'{prefix}defensive_TFL'),
            r.get(f'{prefix}defensive_PD'),     r.get(f'{prefix}interceptions_INT'),
        )

    df_transfers['pre_score']  = df_transfers.apply(lambda r: score_row('pre_',  r), axis=1)
    df_transfers['post_score'] = df_transfers.apply(lambda r: score_row('post_', r), axis=1)
    df_transfers['success_delta'] = df_transfers['post_score'] - df_transfers['pre_score']

    ol_positions = ['OL', 'OT', 'OG', 'C', 'OC']
    df_transfers.loc[df_transfers['position'].isin(ol_positions), 'success_delta'] = None

    df_scored = df_transfers.dropna(subset=['success_delta'])
    print(f"  Transfers with scorable delta: {len(df_scored)}")

    df_scored.to_csv("data/processed/transfers_clean.csv", index=False)
    print("  Saved data/processed/transfers_clean.csv")
    return df_transfers, df_scored


# ── Step 7: Build edge list ───────────────────────────────────────────────────
def build_edges(df_transfers, df_scored, min_transfers=2):
    """Aggregate transfers into a weighted edge list for the graph."""
    print("Building edge list...")
    all_counts  = df_transfers.groupby(['origin', 'destination','position']).size().reset_index(name='transfer_count')
    scored_delta = df_scored.groupby(['origin', 'destination','position']).agg(
        avg_success_delta=('success_delta', 'mean')
    ).reset_index()

    edges = all_counts.merge(scored_delta, on=['origin', 'destination','position'], how='inner')
    edges = edges[edges['transfer_count'] >= min_transfers]

    edges.to_csv("data/processed/edges.csv", index=False)
    print(f"  Edges after threshold ({min_transfers}+): {len(edges)}")
    print("  Saved data/processed/edges.csv")
    return edges


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    wide = build_stats_wide()
    wide = merge_ppa_usage(wide)
    df_transfers = clean_transfers()
    df_transfers = join_recruits(df_transfers)
    df_transfers = attach_pre_post_stats(df_transfers, wide)
    df_transfers, df_scored = compute_success_delta(df_transfers)
    build_edges(df_transfers, df_scored)
    print("\nCleaning complete.")

if __name__ == '__main__':
    run()
