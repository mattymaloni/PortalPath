"""
run.py — PortalPath pipeline orchestrator

Usage:
    python run.py              # fetch + clean + features + rank
    python run.py --fetch      # only fetch raw data from API (requires .env)
    python run.py --clean      # only clean raw data
    python run.py --features   # only compute composite scores and success factors
    python run.py --rank       # only build portal index (PageRank + dev score)
    python run.py --dashboard  # only launch the chart browser
"""
import argparse

def main():
    parser = argparse.ArgumentParser(description='PortalPath pipeline')
    parser.add_argument('--fetch',     action='store_true', help='Fetch raw data from CFBD API')
    parser.add_argument('--clean',     action='store_true', help='Clean raw data')
    parser.add_argument('--features',  action='store_true', help='Compute player scores and success factors')
    parser.add_argument('--rank',      action='store_true', help='Build portal index (PageRank + dev score)')
    parser.add_argument('--dashboard', action='store_true', help='Launch chart browser dashboard')
    args = parser.parse_args()

    run_all = not any([args.fetch, args.clean, args.features, args.rank, args.dashboard])

    if args.fetch or run_all:
        print("Step 1: Fetching raw data")
        from pipeline.fetch import get_client, FETCH_STEPS
        client = get_client()
        for name, fn in FETCH_STEPS.items():
            try:
                fn(client)
            except Exception as e:
                print(f"ERROR in {name}: {e}")

    if args.clean or run_all:
        print("\n Step 2: Cleaning")
        from pipeline.clean import run as clean_run
        wide, df_transfers = clean_run()

    if args.features or run_all:
        print("\n Step 3: Feature engineering")
        if not (args.clean or run_all):
            from pipeline.clean import run as clean_run
            wide, df_transfers = clean_run()
        from pipeline.features import compute_success_delta, compute_success_factor
        df_transfers, df_scored = compute_success_delta(df_transfers)
        df_scored = compute_success_factor(df_scored)

    if args.rank or run_all:
        print("\n Step 4: Portal index (PageRank + dev score)")
        from pipeline.rank import build_index
        build_index()

    if args.dashboard or run_all:
        print("\n Step 5: Launching chart dashboard")
        from viz.dashboard import app as dashboard_app
        print("Starting PortalPath dashboard at http://localhost:8051")
        dashboard_app.run(debug=False, port=8051)

if __name__ == '__main__':
    main()
