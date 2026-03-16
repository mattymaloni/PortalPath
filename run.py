"""
run.py — PortalPath pipeline orchestrator

Usage:
    python run.py            # fetch data + clean + launch map
    python run.py --fetch    # only fetch raw data from API (requires .env)
    python run.py --clean    # only run cleaning pipeline (needs raw CSVs)
    python run.py --map      # only launch the map (needs edges.csv)
"""
import argparse
import os

def main():
    parser = argparse.ArgumentParser(description='PortalPath pipeline')
    parser.add_argument('--fetch', action='store_true', help='Fetch raw data from CFBD API')
    parser.add_argument('--clean', action='store_true', help='Run cleaning pipeline')
    parser.add_argument('--map',   action='store_true', help='Launch interactive map')
    args = parser.parse_args()

    run_all = not any([args.fetch, args.clean, args.map])

    if args.fetch or run_all:
        print("=== Step 1: Fetching raw data ===")
        from pipeline.fetch import (get_client, fetch_transfers, fetch_player_stats,
                                    fetch_recruits, fetch_ppa, fetch_usage)
        client = get_client()
        fetch_transfers(client)
        fetch_player_stats(client)
        fetch_recruits(client)
        fetch_ppa(client)
        fetch_usage(client)

    if args.clean or run_all:
        print("\n=== Step 2: Cleaning & building edges ===")
        from pipeline.clean import run as run_clean
        run_clean()

    if args.map or run_all:
        print("\n=== Step 3: Launching map ===")
        if not os.path.exists("data/processed/edges.csv"):
            print("ERROR: edges.csv not found. Run --clean first.")
            return
        from viz.map import app
        print("Starting PortalPath map at http://localhost:8050")
        app.run(debug=False, port=8050)

if __name__ == '__main__':
    main()
