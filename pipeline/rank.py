"""
rank.py — PageRank and development score for transfer portal schools

  PageRank      — iterative prestige diffusion using pre_score weights
                  (how central is a school in the transfer network?)

  Development   — success-factor-weighted avg post_score per destination
                  (do players actually produce after transferring here?)

  Portal Index  — 0.3 * PageRank + 0.7 * dev_score_norm

Usage:
    python pipeline/rank.py                  # PageRank
    python pipeline/rank.py --index          # PageRank + dev score index
    python pipeline/rank.py --dev            # development score only
    python pipeline/rank.py --years 2021 2022 2023
"""
import argparse
import numpy as np
import pandas as pd


def build_graph(df, years):
    """
    Build a weighted directed graph from transfer data.
    Edge A -> B weight = avg(pre_score) * log(1 + count) for all transfers A->B in given years.
    Returns adjacency dict: {origin: {destination: weight}}
    """
    df = df[df['year'].isin(years)].copy()
    df = df[df['pre_score'] > 0]  # only players with a real signal

    edges = (
        df.groupby(['origin', 'destination'])
        .agg(avg_pre=('pre_score', 'mean'), count=('pre_score', 'count'))
        .reset_index()
    )
    edges['weight'] = edges['avg_pre'] * np.log1p(edges['count'])

    graph = {}
    for _, row in edges.iterrows():
        if row['origin'] not in graph:
            graph[row['origin']] = {}
        graph[row['origin']][row['destination']] = row['weight']

    return graph


def pagerank(graph, damping=0.85, max_iter=100, tol=1e-6):
    """
    Standard PageRank on a weighted directed graph.
    Each node distributes its prestige to neighbors proportional to edge weight.
    """
    nodes = set(graph.keys()) | {d for neighbors in graph.values() for d in neighbors}
    N = len(nodes)
    nodes = sorted(nodes)
    node_idx = {n: i for i, n in enumerate(nodes)}

    # Normalize outgoing weights per node
    out_weight = {n: sum(graph.get(n, {}).values()) for n in nodes}

    scores = np.ones(N) / N

    for _ in range(max_iter):
        new_scores = np.ones(N) * (1 - damping) / N

        for src, neighbors in graph.items():
            if out_weight[src] == 0:
                continue
            src_i = node_idx[src]
            for dst, w in neighbors.items():
                dst_i = node_idx[dst]
                new_scores[dst_i] += damping * scores[src_i] * (w / out_weight[src])

        delta = np.abs(new_scores - scores).sum()
        scores = new_scores
        if delta < tol:
            break

    return pd.Series(scores, index=nodes).sort_values(ascending=False)


_POSITION_WEIGHT = {
    'QB':   1.4, 'DUAL': 1.4,
    'WR':   1.0, 'RB':   1.0, 'FB':   1.0,
    'EDGE': 1.0, 'DE':   1.0, 'RUSH': 1.0, 'WDE':  1.0, 'SDE':  1.0,
    'TE':   0.9, 'PRO':  0.9,
    'LB':   0.9, 'ILB':  0.9, 'OLB':  0.9, 'MLB':  0.9,
    'CB':   0.9, 'S':    0.9, 'DB':   0.9, 'SAF':  0.9, 'FS':   0.9, 'SS':   0.9,
    'DL':   0.9, 'DT':   0.9, 'NT':   0.9, 'IDL':  0.9,
    'K':    0.55, 'PK':  0.55,
    'P':    0.45,
    'LS':   0.0,  # excluded like OL
}


def build_development_rate(df, years, min_transfers=10):
    """
    For each destination school, compute the success-factor-weighted average
    position-adjusted post_score of incoming transfers.

    post_score is first converted to a within-position percentile (0-1) across
    all transfers in the given years, then multiplied by a position importance
    weight (QB=1.4 down to P=0.45) so cross-position comparisons are meaningful.

    Answers: "do players actually produce after transferring here?"
    Weighted by success_factor so Tier 1 players (reliable signal) count more
    than Tier 3 players (never played anywhere).
    """
    df = df[df['year'].isin(years)].copy()
    df = df[df['post_score'].notna() & df['success_factor'].notna()]

    # Percentile rank within each position group (0-1), zero-scorers stay at 0
    pos_col = df['position'].str.upper().str.strip()
    df['_pos_pct'] = df.groupby(pos_col)['post_score'].rank(pct=True, method='min')
    df.loc[df['post_score'] == 0, '_pos_pct'] = 0
    df['_weighted_score'] = df['_pos_pct'] * pos_col.map(_POSITION_WEIGHT).fillna(0.9)

    def weighted_avg_post(group):
        w = group['success_factor']
        total_w = w.sum()
        if total_w == 0:
            return 0
        return (group['_weighted_score'] * w).sum() / total_w

    grouped = df.groupby('destination').apply(
        lambda g: pd.Series({
            'dev_score': weighted_avg_post(g),
            'transfer_count': len(g),
        }),
        include_groups=False,
    ).reset_index()

    grouped = grouped[grouped['transfer_count'] >= min_transfers]

    # Normalize 0-1
    grouped['dev_score_norm'] = (grouped['dev_score'] - grouped['dev_score'].min()) / \
                                 (grouped['dev_score'].max() - grouped['dev_score'].min())

    return grouped.sort_values('dev_score', ascending=False).reset_index(drop=True)


def run_pagerank(years=None):
    df = pd.read_csv("data/processed/scored_transfers.csv", low_memory=False)
    sp = pd.read_csv("data/raw/sp_ratings.csv")
    fbs_schools = set(sp['team'].unique())

    if years is None:
        years = sorted(df['year'].unique())

    graph = build_graph(df, years)
    pr = pagerank(graph)

    # Filter to FBS only and normalize 0-1
    pr = pr[pr.index.isin(fbs_schools)]
    pr = (pr - pr.min()) / (pr.max() - pr.min())
    pr.name = 'pagerank'

    print(f"\nPageRank — trained on {min(years)}–{max(years)} ({len(pr)} FBS schools):")
    print(f"{'Rank':<5} {'School':<28} {'PageRank':>10}")
    print("-" * 46)
    for i, (school, score) in enumerate(pr.items()):
        print(f"{i+1:<5} {school:<28} {score:>10.4f}")

    return pr


def run_development_rate(years=None):
    df = pd.read_csv("data/processed/scored_transfers.csv", low_memory=False)
    sp = pd.read_csv("data/raw/sp_ratings.csv")
    fbs_schools = set(sp['team'].unique())

    if years is None:
        years = sorted(df['year'].unique())

    dev = build_development_rate(df, years)
    dev = dev[dev['destination'].isin(fbs_schools)].reset_index(drop=True)

    print(f"\nDevelopment Score — trained on {min(years)}–{max(years)} ({len(dev)} FBS schools):")
    print(f"{'Rank':<5} {'School':<28} {'Dev Score':>10} {'Transfers':>10}")
    print("-" * 56)
    for i, row in dev.iterrows():
        print(f"{i+1:<5} {row['destination']:<28} {row['dev_score']:>10.4f} {int(row['transfer_count']):>10}")

    return dev


def _compute_index(df, fbs_schools, years, min_transfers=10):
    """Build portal index for a given set of years. Returns sorted DataFrame."""
    from scipy.stats import spearmanr

    graph = build_graph(df, years)
    pr = pagerank(graph)
    pr = pr[pr.index.isin(fbs_schools)]
    pr = (pr - pr.min()) / (pr.max() - pr.min())

    dev = build_development_rate(df, years, min_transfers=min_transfers)
    dev = dev[dev['destination'].isin(fbs_schools)].reset_index(drop=True)

    index = pr.reset_index()
    index.columns = ['school', 'pagerank']
    index = index.merge(
        dev[['destination', 'dev_score', 'dev_score_norm']].rename(columns={'destination': 'school'}),
        on='school', how='inner'
    )
    index['portal_index'] = 0.3 * index['pagerank'] + 0.7 * index['dev_score_norm']
    return index.sort_values('portal_index', ascending=False).reset_index(drop=True)


def _print_index(index, label):
    print(f"\n{label} ({len(index)} schools):")
    print(f"{'Rank':<5} {'School':<28} {'Index':>8} {'PageRank':>10} {'Dev Score':>10}")
    print("-" * 64)
    for i, row in index.iterrows():
        print(f"{i+1:<5} {row['school']:<28} {row['portal_index']:>8.4f} "
              f"{row['pagerank']:>10.4f} {row['dev_score_norm']:>10.4f}")


def _validate(df, fbs_schools, index, test_year):
    from scipy.stats import spearmanr
    test = df[(df['year'] == test_year) & df['destination'].isin(fbs_schools) & df['post_score'].notna()]
    merged = test.merge(index[['school', 'portal_index']], left_on='destination', right_on='school', how='left')
    merged = merged[merged['portal_index'].notna()]
    r, p = spearmanr(merged['portal_index'], merged['post_score'])
    sig = "YES" if r > 0 and p < 0.05 else "WEAK/NO"
    print(f"  Validation {test_year}: r={r:.3f}  p={p:.4f}  n={len(merged)} transfers  → {sig}")


def build_index(min_transfers=10):
    df = pd.read_csv("data/processed/scored_transfers.csv", low_memory=False)
    sp = pd.read_csv("data/raw/sp_ratings.csv")
    fbs_schools = set(sp['team'].unique())
    all_years = sorted(df['year'].unique())
    scored_years = [y for y in all_years if y < 2026]  # exclude in-progress seasons
    results = {}

    # All-time index (completed seasons only)
    all_time = _compute_index(df, fbs_schools, scored_years, min_transfers)
    _print_index(all_time, f"All-Time Portal Index ({min(scored_years)}–{max(scored_years)})")
    results['all_time'] = all_time
    all_time.to_csv("data/processed/portal_index_alltime.csv", index=False)

    # Per-year index with same-year validation
    print("\n" + "="*64)
    print("PER-YEAR PORTAL INDEX")
    print("="*64)

    for year in all_years:
        index = _compute_index(df, fbs_schools, [year], min_transfers)
        _print_index(index, f"{year} Portal Index")
        _validate(df, fbs_schools, index, year)
        results[year] = index
        index.to_csv(f"data/processed/portal_index_{year}.csv", index=False)

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--years', type=int, nargs='+', default=None)
    parser.add_argument('--dev', action='store_true', help='Show development score')
    parser.add_argument('--index', action='store_true', help='Build combined portal index (all-time + per-year)')
    args = parser.parse_args()

    if args.dev:
        run_development_rate(years=args.years)
    elif args.index:
        build_index()
    else:
        run_pagerank(years=args.years)
