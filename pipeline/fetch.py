import os
import sys
import cfbd
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def get_client():
    configuration = cfbd.Configuration()
    configuration.access_token = os.getenv('CFBD_API_KEY')
    if not configuration.access_token:
        raise ValueError("CFBD_API_KEY not set.")
    return cfbd.ApiClient(configuration)


def fetch_transfers(client, years=range(2021, 2027)):
    api = cfbd.PlayersApi(client)
    rows = []
    for year in years:
        print(f"Pulling transfers {year}...")
        try:
            results = api.get_transfer_portal(year=year)
        except Exception as e:
            print(f"  {year} skipped: {e}")
            continue
        for r in results:
            rows.append({
                'year': year,
                'first_name': r.first_name,
                'last_name': r.last_name,
                'position': r.position,
                'origin': r.origin,
                'destination': r.destination,
                'rating': r.rating,
                'stars': r.stars,
                'eligibility': r.eligibility,
            })
        print(f"  {len(results)} transfers found")
    df = pd.DataFrame(rows)
    df.to_csv("data/raw/transfers.csv", index=False)
    print(f"Saved data/raw/transfers.csv ({len(df)} rows)")
    return df


def fetch_player_stats(client, years=range(2020, 2026)):
    api = cfbd.StatsApi(client)
    rows = []
    for year in years:
        print(f"Pulling stats {year}...")
        try:
            results = api.get_player_season_stats(year=year)
        except Exception as e:
            print(f"  {year} skipped: {e}")
            continue
        for r in results:
            rows.append({
                'year': year,
                'player_id': r.player_id,
                'player': r.player,
                'team': r.team,
                'conference': r.conference,
                'category': r.category,
                'stat_type': r.stat_type,
                'stat': r.stat,
            })
        print(f"  {len(results)} stat rows found")
    df = pd.DataFrame(rows)
    df.to_csv("data/raw/player_stats.csv", index=False)
    print(f"Saved data/raw/player_stats.csv ({len(df)} rows)")
    return df


def fetch_recruits(client, years=range(2017, 2026)):
    api = cfbd.RecruitingApi(client)
    rows = []
    for year in years:
        print(f"Pulling recruits {year}...")
        try:
            results = api.get_recruits(year=year)
        except Exception as e:
            print(f"  {year} skipped: {e}")
            continue
        for r in results:
            rows.append({
                'year': year,
                'athlete_id': r.athlete_id,
                'name': r.name,
                'committed_to': r.committed_to,
                'position': r.position,
                'stars': r.stars,
                'rating': r.rating,
                'ranking': r.ranking,
            })
        print(f"  {len(results)} recruits found")
    df = pd.DataFrame(rows)
    df.to_csv("data/raw/recruits.csv", index=False)
    print(f"Saved data/raw/recruits.csv ({len(df)} rows)")
    return df


def fetch_ppa(client, years=range(2020, 2026)):
    api = cfbd.MetricsApi(client)
    rows = []
    for year in years:
        print(f"Pulling PPA {year}...")
        try:
            results = api.get_predicted_points_added_by_player_season(year=year)
        except Exception as e:
            print(f"  {year} skipped: {e}")
            continue
        for r in results:
            rows.append({
                'year': year,
                'player': r.name,
                'team': r.team,
                'position': r.position,
                'avg_ppa_total': r.average_ppa.all,
                'avg_ppa_rushing': r.average_ppa.rush,
                'avg_ppa_passing': r.average_ppa.var_pass,
            })
        print(f"  {len(results)} PPA rows found")
    df = pd.DataFrame(rows)
    df.to_csv("data/raw/ppa.csv", index=False)
    print(f"Saved data/raw/ppa.csv ({len(df)} rows)")
    return df



def fetch_usage(client, years=range(2020, 2026)):
    api = cfbd.PlayersApi(client)
    rows = []
    for year in years:
        print(f"Pulling usage {year}...")
        try:
            results = api.get_player_usage(year=year)
        except Exception as e:
            print(f"  {year} skipped: {e}")
            continue
        for r in results:
            rows.append({
                'year': year,
                'player_id': r.id,
                'player': r.name,
                'team': r.team,
                'position': r.position,
                'usage_overall': r.usage.overall,
                'usage_rush': r.usage.rush,
                'usage_pass': r.usage.var_pass,
            })
        print(f"  {len(results)} usage rows found")
    df = pd.DataFrame(rows)
    df.to_csv("data/raw/usage.csv", index=False)
    print(f"Saved data/raw/usage.csv ({len(df)} rows)")
    return df


def fetch_sp_ratings(client, years=range(2020, 2026)):
    api = cfbd.RatingsApi(client)
    rows = []
    for year in years:
        print(f"Pulling SP+ ratings {year}...")
        try:
            results = api.get_sp(year=year)
        except Exception as e:
            print(f"  {year} skipped: {e}")
            continue
        for r in results:
            rows.append({
                'year': year,
                'team': r.team,
                'conference': r.conference,
                'sp_rating': r.rating,
                'sp_offense': r.offense.rating if r.offense else None,
                'sp_defense': r.defense.rating if r.defense else None,
            })
        print(f"  {len(results)} SP+ rows found")
    df = pd.DataFrame(rows)
    df.to_csv("data/raw/sp_ratings.csv", index=False)
    print(f"Saved data/raw/sp_ratings.csv ({len(df)} rows)")
    return df


FETCH_STEPS = {
    'transfers':         fetch_transfers,
    'player_stats':      fetch_player_stats,
    'recruits':          fetch_recruits,
    'ppa':               fetch_ppa,
    'usage':             fetch_usage,

    'sp_ratings':        fetch_sp_ratings,
}

if __name__ == '__main__':
    client = get_client()

    # Run a single step:  python pipeline/fetch.py sp_ratings
    # Run everything:     python pipeline/fetch.py
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(FETCH_STEPS.keys())

    unknown = [t for t in targets if t not in FETCH_STEPS]
    if unknown:
        print(f"Unknown steps: {unknown}. Available: {list(FETCH_STEPS.keys())}")
        sys.exit(1)

    failed = []
    for name in targets:
        try:
            FETCH_STEPS[name](client)
        except Exception as e:
            print(f"ERROR in {name}: {e}")
            failed.append(name)

    if failed:
        print(f"\nCompleted with errors in: {', '.join(failed)}")
    else:
        print("\nAll raw data fetched.")
