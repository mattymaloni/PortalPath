import pandas as pd


def build_stats_wide():
    """Pivot raw player stats from long format to one row per player-season."""
    print("Building stats wide")
    df = pd.read_csv("data/raw/player_stats.csv")

    keep = {
        'rushing':       ['YDS', 'CAR', 'TD', 'AVG'],
        'receiving':     ['YDS', 'REC', 'TD', 'AVG', 'LONG'],
        'passing':       ['YDS', 'TD', 'ATT', 'INT', 'PCT', 'COMPLETIONS', 'QBR'],
        'defensive':     ['TOT', 'SOLO', 'SACKS', 'TFL', 'PD', 'QB HUR', 'TD'],
        'interceptions': ['INT', 'YDS', 'TD'],
        'fumbles':       ['FUM', 'LOST'],
        'kicking':       ['FGM', 'FGA', 'XPM', 'XPA', 'PTS', 'LONG'],
        'punting':       ['NO', 'YDS', 'AVG', 'LONG', 'In 20', 'TB'],
        'kickReturns':   ['YDS', 'TD', 'AVG', 'NO'],
        'puntReturns':   ['YDS', 'TD', 'AVG', 'NO'],
    }
    mask = df.apply(
        lambda row: row['category'] in keep and row['stat_type'] in keep[row['category']], axis=1
    )
    df = df[mask].copy()
    df['col'] = df['category'] + '_' + df['stat_type']

    # Carry conference through, take first value per player-season
    conf_map = df.groupby(['year', 'player_id', 'player', 'team'])['conference'].first().reset_index()

    wide = df.pivot_table(
        index=['year', 'player_id', 'player', 'team'],
        columns='col',
        values='stat',
        aggfunc='first',
    ).reset_index()
    wide.columns.name = None
    wide = wide.merge(conf_map, on=['year', 'player_id', 'player', 'team'], how='left')

    wide['yards_per_carry'] = wide.get('rushing_YDS', 0) / wide.get('rushing_CAR', 1).replace(0, 1)
    wide['yards_per_rec']   = wide.get('receiving_YDS', 0) / wide.get('receiving_REC', 1).replace(0, 1)
    fga = wide.get('kicking_FGA', pd.Series(1, index=wide.index)).replace(0, 1)
    xpa = wide.get('kicking_XPA', pd.Series(1, index=wide.index)).replace(0, 1)
    wide['kicking_FG_PCT'] = wide.get('kicking_FGM', 0) / fga
    wide['kicking_XP_PCT'] = wide.get('kicking_XPM', 0) / xpa

    print(f"  Stats wide: {wide.shape}")
    return wide


def merge_ppa_usage(wide):
    """Join PPA and usage onto the wide stats table by player+team+year."""
    print("Merging PPA and usage...")
    df_ppa   = pd.read_csv("data/raw/ppa.csv")
    df_usage = pd.read_csv("data/raw/usage.csv")

    for df in [wide, df_ppa, df_usage]:
        df['player_norm'] = df['player'].str.lower().str.strip()
        df['team_norm']   = df['team'].str.lower().str.strip()

    # Dedup before merging to prevent inflation when a player appears multiple times in PPA or usage for the same year/team
    df_ppa   = df_ppa.drop_duplicates(subset=['year', 'player_norm', 'team_norm'])
    df_usage = df_usage.drop_duplicates(subset=['year', 'player_norm', 'team_norm'])

    wide = wide.merge(
        df_ppa[['year', 'player_norm', 'team_norm', 'avg_ppa_total', 'avg_ppa_rushing', 'avg_ppa_passing']],
        on=['year', 'player_norm', 'team_norm'], how='left',
    )
    wide = wide.merge(
        df_usage[['year', 'player_norm', 'team_norm', 'position', 'usage_overall', 'usage_rush', 'usage_pass']],
        on=['year', 'player_norm', 'team_norm'], how='left',
    )

    wide.to_csv("data/processed/stats_clean.csv", index=False)
    print("  Saved data/processed/stats_clean.csv")
    return wide


def clean_transfers():
    """Drop uncommitted portal entries and normalize names for joining."""
    print("Cleaning transfers")
    df = pd.read_csv("data/raw/transfers.csv")
    df = df.dropna(subset=['destination'])
    df['player_norm']      = (df['first_name'] + ' ' + df['last_name']).str.lower().str.strip()
    df['origin_norm']      = df['origin'].str.lower().str.strip()
    df['destination_norm'] = df['destination'].str.lower().str.strip()
    before = len(df)
    df = df.drop_duplicates(subset=['year', 'player_norm', 'origin_norm', 'destination_norm'])
    print(f"  Transfers with destination: {len(df)} ({before - len(df)} duplicates removed)")
    return df


def join_recruits(df_transfers):
    """Attach recruiting star rating to each transfer row"""
    print("Joining recruiting data")
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


def attach_pre_post_stats(df_transfers, stats_wide):
    """Join the season before and after each transfer onto the transfer row"""
    print("Attaching pre/post stats")
    join_keys = {'year', 'player_id', 'player', 'team', 'player_norm', 'team_norm'}
    stat_cols = [c for c in stats_wide.columns if c not in join_keys]
    cols = ['year', 'player_norm', 'team_norm'] + stat_cols
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

    # Post stats: most transfers play same year. Try same-year join first, fall back to year+1 for players who sat out.
    def make_post(shift):
        p = stats_key.copy()
        p.columns = [
            'post_year' if c == 'year'
            else c if c in ('player_norm', 'team_norm')
            else 'post_' + c
            for c in p.columns
        ]
        p['year'] = p['post_year'] - shift
        return p.rename(columns={'team_norm': 'destination_norm'})

    post_same = make_post(0)   # played same year 
    post_next = make_post(1)   # sat out a year 

    df_transfers = df_transfers.merge(pre, on=['year', 'player_norm', 'origin_norm'], how='left')

    # Merge same-year post stats
    df_transfers = df_transfers.merge(post_same, on=['year', 'player_norm', 'destination_norm'], how='left')

    # For rows where same-year join found nothing, try year+1
    post_cols = [c for c in df_transfers.columns if c.startswith('post_')]
    missing = df_transfers[post_cols].isna().all(axis=1)
    if missing.any():
        fallback = df_transfers[missing].drop(columns=post_cols).merge(
            post_next, on=['year', 'player_norm', 'destination_norm'], how='left'
        )
        df_transfers.loc[missing, post_cols] = fallback[post_cols].values

    print(f"  Post stats: {(~missing).sum()} same-year, {missing.sum()} fallback to year+1")
    return df_transfers


def run():
    wide = build_stats_wide()
    wide = merge_ppa_usage(wide)
    df_transfers = clean_transfers()
    df_transfers = join_recruits(df_transfers)
    df_transfers = attach_pre_post_stats(df_transfers, wide)
    return wide, df_transfers


if __name__ == '__main__':
    run()
    print("\nCleaning complete")
