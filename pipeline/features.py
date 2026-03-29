"""
How players success for a year is scored based on their stats
Validate through testingn and comparing with PPA and "eye-check" (is 2025 Mendoza cobsidered at least top 3, etc)
"""
import math
import pandas as pd
from scipy.stats import spearmanr


def _n(val):
    try:
        return 0 if (val is None or math.isnan(float(val))) else float(val)
    except (TypeError, ValueError):
        return 0


QB_POS   = {'QB', 'DUAL'}
RB_POS   = {'RB', 'FB'}
WR_POS   = {'WR'}
TE_POS   = {'TE', 'PRO'}
OL_POS   = {'OL', 'OT', 'OG', 'C', 'OC', 'IOL', 'LS'}
DB_POS   = {'CB', 'S', 'DB', 'SAF', 'FS', 'SS'}
LB_POS   = {'LB', 'ILB', 'OLB', 'MLB'}
EDGE_POS = {'EDGE', 'DE', 'RUSH', 'WDE', 'SDE'}
DL_POS   = {'DL', 'DT', 'NT', 'IDL'}
K_POS    = {'K', 'PK'}
P_POS    = {'P'}
ATH_POS  = {'ATH', 'SPEC', 'WB', 'APB'}


def _eff_mult(efficiency, baseline, scale=0.3):
    """
    Efficiency multiplier around 1.0.
    Above baseline boosts the score, below baseline discounts it.
    scale controls how much it moves (default 30%)
    """
    return 1.0 + scale * ((efficiency / max(baseline, 0.001)) - 1.0)


def _score_qb(r, pfx):
    ppa   = _n(r.get(f'{pfx}avg_ppa_total'))
    usage = _n(r.get(f'{pfx}usage_overall'))
    yds   = _n(r.get(f'{pfx}passing_YDS'))
    att   = _n(r.get(f'{pfx}passing_ATT'))
    td    = _n(r.get(f'{pfx}passing_TD'))
    ints  = _n(r.get(f'{pfx}passing_INT'))
    pct   = _n(r.get(f'{pfx}passing_PCT'))
    rush  = _n(r.get(f'{pfx}rushing_YDS'))
    fum   = _n(r.get(f'{pfx}fumbles_LOST'))
    # yards per attempt as efficiency multiplier, only apply with enough attempts
    ypa_mult = _eff_mult(yds / max(att, 1), baseline=7.5) if att >= 50 else 1.0
    base = ((0.35 * ppa) + (0.20 * usage) + (0.15 * (yds / 3000))
            + (0.10 * (td / 20)) + (0.08 * (pct / 0.65))
            + (0.05 * (rush / 500)) - (0.05 * (ints / 10)) - (0.02 * (fum / 5)))
    return base * ypa_mult


def _score_skill(r, pfx, rush_w=0.0, recv_w=0.0):
    ppa      = _n(r.get(f'{pfx}avg_ppa_total'))
    usage    = _n(r.get(f'{pfx}usage_overall'))
    rush_yds = _n(r.get(f'{pfx}rushing_YDS'))
    rush_car = _n(r.get(f'{pfx}rushing_CAR'))
    rush_td  = _n(r.get(f'{pfx}rushing_TD'))
    rec_yds  = _n(r.get(f'{pfx}receiving_YDS'))
    rec      = _n(r.get(f'{pfx}receiving_REC'))
    rec_td   = _n(r.get(f'{pfx}receiving_TD'))
    fum      = _n(r.get(f'{pfx}fumbles_LOST'))
    kr_yds   = _n(r.get(f'{pfx}kickReturns_YDS'))
    pr_yds   = _n(r.get(f'{pfx}puntReturns_YDS'))
    kr_td    = _n(r.get(f'{pfx}kickReturns_TD'))
    pr_td    = _n(r.get(f'{pfx}puntReturns_TD'))
    return_bonus = (kr_yds + pr_yds) / 500 + (kr_td + pr_td) * 0.05
    # efficiency multipliers, only apply with enough volume to be meaningful
    ypc_mult = _eff_mult(rush_yds / max(rush_car, 1), baseline=4.5) if (rush_w > 0 and rush_car >= 30) else 1.0
    ypr_mult = _eff_mult(rec_yds  / max(rec, 1),      baseline=13.0) if (recv_w > 0 and rec >= 15) else 1.0
    rush_contrib = rush_w * ((rush_yds / 1000) + (rush_td / 10)) * ypc_mult
    recv_contrib = recv_w * ((rec_yds  / 800)  + (rec_td  /  8)) * ypr_mult
    return ((0.40 * ppa) + (0.25 * usage)
            + rush_contrib + recv_contrib
            + (0.05 * return_bonus) - (0.03 * (fum / 5)))


def _score_defender(r, pfx, sacks_w=1.0, coverage_w=1.0):
    ppa    = _n(r.get(f'{pfx}avg_ppa_total'))
    usage  = _n(r.get(f'{pfx}usage_overall'))
    tot    = _n(r.get(f'{pfx}defensive_TOT'))
    solo   = _n(r.get(f'{pfx}defensive_SOLO'))
    sacks  = _n(r.get(f'{pfx}defensive_SACKS'))
    tfl    = _n(r.get(f'{pfx}defensive_TFL'))
    qb_hur = _n(r.get(f'{pfx}defensive_QB HUR'))
    pd_    = _n(r.get(f'{pfx}defensive_PD'))
    ints   = _n(r.get(f'{pfx}interceptions_INT'))
    int_td = _n(r.get(f'{pfx}interceptions_TD'))
    # sack rate as efficiency multiplier for pass rushers, baseline ~0.05 sacks per tackle
    sack_rate_mult = _eff_mult(sacks / max(tot, 1), baseline=0.05) if sacks_w > 1.0 else 1.0
    havoc    = (tot / 10) + (solo / 12) + (sacks_w * sacks / 5) + (tfl / 6) + (qb_hur * 0.5 / 5)
    coverage = coverage_w * ((pd_ / 8) + (ints / 3) + (int_td * 0.1))
    return ((0.35 * ppa) + (0.20 * usage) + (0.30 * havoc) + (0.15 * coverage)) * sack_rate_mult


def _score_kicker(r, pfx):
    fg_pct = _n(r.get(f'{pfx}kicking_FG_PCT'))
    xp_pct = _n(r.get(f'{pfx}kicking_XP_PCT'))
    pts    = _n(r.get(f'{pfx}kicking_PTS'))
    long_  = _n(r.get(f'{pfx}kicking_LONG'))
    return (0.40 * fg_pct) + (0.20 * xp_pct) + (0.25 * (pts / 80)) + (0.15 * (long_ / 55))


def _score_punter(r, pfx):
    avg_  = _n(r.get(f'{pfx}punting_AVG'))
    in20  = _n(r.get(f'{pfx}punting_In 20'))
    no    = _n(r.get(f'{pfx}punting_NO'))
    tb    = _n(r.get(f'{pfx}punting_TB'))
    long_ = _n(r.get(f'{pfx}punting_LONG'))
    return (0.35 * (avg_ / 45)) + (0.30 * (in20 / max(no, 1))) + (0.20 * (long_ / 60)) - (0.15 * (tb / max(no, 1)))


def composite_score(position, r, pfx):
    pos = str(position).upper().strip()
    if pos in QB_POS:   return _score_qb(r, pfx)
    if pos in RB_POS:   return _score_skill(r, pfx, rush_w=0.25, recv_w=0.10)
    if pos in WR_POS:   return _score_skill(r, pfx, rush_w=0.02, recv_w=0.33)
    if pos in TE_POS:   return _score_skill(r, pfx, rush_w=0.02, recv_w=0.28)
    if pos in DB_POS:   return _score_defender(r, pfx, sacks_w=0.5,  coverage_w=1.5)
    if pos in LB_POS:   return _score_defender(r, pfx, sacks_w=1.0,  coverage_w=1.0)
    if pos in EDGE_POS: return _score_defender(r, pfx, sacks_w=2.0,  coverage_w=0.3)
    if pos in DL_POS:   return _score_defender(r, pfx, sacks_w=2.0,  coverage_w=0.1)
    if pos in K_POS:    return _score_kicker(r, pfx)
    if pos in P_POS:    return _score_punter(r, pfx)
    if pos in OL_POS:   return None
    return _score_skill(r, pfx, rush_w=0.15, recv_w=0.20)


def compute_success_delta(df_transfers):
    """Compute pre/post composite scores and their delta for each transfer."""
    print("Computing success delta")
    df_transfers['pre_score']  = df_transfers.apply(
        lambda r: composite_score(r['position'], r, 'pre_'),  axis=1)
    df_transfers['post_score'] = df_transfers.apply(
        lambda r: composite_score(r['position'], r, 'post_'), axis=1)
    df_transfers['success_delta'] = df_transfers['post_score'] - df_transfers['pre_score']

    df_scored = df_transfers.dropna(subset=['success_delta'])
    print(f"  Transfers with scorable delta: {len(df_scored)}")
    df_scored.to_csv("data/processed/transfers_clean.csv", index=False)
    print("  Saved data/processed/transfers_clean.csv")
    return df_transfers, df_scored


def compute_success_factor(df_scored):
    """
    Gives each transfer a success_factor (0-1) based on how reliable their pre_score is.

    Tier 1 — played before transferring, met volume thresholds
    Tier 2 — has stats from an earlier season (may have been injured)
    Tier 3 — no stats anywhere before transferring
    """
    print("Computing player success factors")

    raw_stats = pd.read_csv("data/raw/player_stats.csv")
    raw_stats['player_norm'] = raw_stats['player'].str.lower().str.strip()
    active_seasons = set(zip(raw_stats['player_norm'], raw_stats['year'].astype(int)))

    pre_score_max = df_scored['pre_score'].max() or 1.0

    def _meets_volume(row, pfx='pre_'):
        """Player had enough volume in their pre-transfer year to be a reliable signal"""
        return (
            _n(row.get(f'{pfx}passing_ATT'))   >= 50 or
            _n(row.get(f'{pfx}rushing_CAR'))   >= 30 or
            _n(row.get(f'{pfx}receiving_REC')) >= 15 or
            _n(row.get(f'{pfx}defensive_TOT')) >= 20
        )

    def get_tier(row):
        if row['pre_score'] > 0 and _meets_volume(row):
            return 1
        pnorm  = str(row.get('player_norm', '')).lower().strip()
        pre_yr = int(row['pre_year']) if pd.notna(row.get('pre_year')) else 0
        if (pnorm, pre_yr - 1) in active_seasons or (pnorm, pre_yr - 2) in active_seasons:
            return 2
        return 3

    def get_factor(row):
        tier   = row['_tier']
        pnorm  = str(row.get('player_norm', '')).lower().strip()
        pre_yr = int(row['pre_year']) if pd.notna(row.get('pre_year')) else 0

        if tier == 1:
            return max(row['pre_score'] / pre_score_max, 0.15)

        base = 0.35 if tier == 2 else 0.10
        stars = row.get('recruit_stars')
        if pd.notna(stars) and stars > 0:
            base += (stars / 5) * 0.15
        return base

    df_scored = df_scored.copy()
    df_scored['_tier']          = df_scored.apply(get_tier, axis=1)
    df_scored['success_factor'] = df_scored.apply(get_factor, axis=1)

    t1 = (df_scored['_tier'] == 1).sum()
    t2 = (df_scored['_tier'] == 2).sum()
    t3 = (df_scored['_tier'] == 3).sum()
    print(f"  Tier 1 (played):          {t1}")
    print(f"  Tier 2 (possible injury): {t2}")
    print(f"  Tier 3 (never played):    {t3}")

    df_scored = df_scored.drop(columns=['_tier'])
    df_scored.to_csv("data/processed/scored_transfers.csv", index=False)
    print("  Saved data/processed/scored_transfers.csv")
    return df_scored


def _validate_single_year(year, stats_all, sp):
    df = stats_all[stats_all['year'] == year].copy()
    df = df[df['avg_ppa_total'].notna()].copy()
    df = df[
        (df['passing_ATT'].fillna(0) >= 50) |
        (df['rushing_CAR'].fillna(0) >= 30) |
        (df['receiving_REC'].fillna(0) >= 15) |
        (df['defensive_TOT'].fillna(0) >= 20)
    ].copy()

    sp_year = sp[sp['year'] == year][['team', 'conference', 'sp_rating']].copy()
    conf_sp = sp_year.groupby('conference')['sp_rating'].mean()
    conf_sp_norm = (conf_sp - conf_sp.min()) / (conf_sp.max() - conf_sp.min())
    conf_multiplier = (0.75 + 0.40 * conf_sp_norm).to_dict()
    df['conf_multiplier'] = df['conference'].map(conf_multiplier).fillna(0.65)

    position_groups = {
        'QB': QB_POS, 'RB': RB_POS, 'WR': WR_POS, 'TE': TE_POS,
        'DB': DB_POS, 'LB': LB_POS, 'EDGE': EDGE_POS, 'DL': DL_POS,
    }

    results = []
    for group_name, pos_set in position_groups.items():
        if not df['position'].notna().any():
            continue
        subset = df[df['position'].str.upper().isin(pos_set)].copy()
        if len(subset) < 10:
            continue
        subset['composite'] = subset.apply(
            lambda r: composite_score(r['position'], r.to_dict(), ''), axis=1
        )
        subset = subset[subset['composite'].notna()].copy()
        subset['composite'] = subset['composite'] * subset['conf_multiplier']
        if len(subset) < 10:
            continue
        subset['composite_rank'] = subset['composite'].rank(ascending=False)
        subset['ppa_rank']       = subset['avg_ppa_total'].rank(ascending=False)
        corr, _ = spearmanr(subset['composite_rank'], subset['ppa_rank'])
        results.append({'year': year, 'position': group_name, 'n': len(subset),
                        'correlation': corr, 'subset': subset})
    return results


def validate_weights(years=None):
    """
    Validate composite_score weights against PPA rankings across all available years.
    Shows per-year top 10 lists and an aggregate correlation summary.
    """
    stats = pd.read_csv("data/processed/stats_clean.csv")
    sp    = pd.read_csv("data/raw/sp_ratings.csv")

    if years is None:
        years = sorted(stats['year'].unique())

    all_results = []
    for year in years:
        year_results = _validate_single_year(year, stats, sp)
        all_results.extend(year_results)

    # Per-year top 10 detail
    for year in years:
        print(f"\n{'='*60}")
        print(f"  {year}")
        print(f"{'='*60}")
        year_data = [r for r in all_results if r['year'] == year]
        for r in year_data:
            status = 'WEAK' if r['correlation'] < 0.6 else '✓'
            print(f"\n  {r['position']} ({r['n']} players)  corr={r['correlation']:.3f} {status}")
            print(f"  {'Player':<25} {'Team':<20} {'Composite':>10} {'PPA Rank':>10}")
            print(f"  {'-'*25} {'-'*20} {'-'*10} {'-'*10}")
            top10 = r['subset'].nsmallest(10, 'composite_rank')
            for _, row in top10.iterrows():
                print(f"  {str(row['player']):<25} {str(row['team']):<20} {row['composite']:>10.3f} {int(row['ppa_rank']):>10}")

    # Aggregate summary across all years
    print(f"\n{'='*60}")
    print("AGGREGATE SUMMARY (all years)")
    print(f"{'='*60}")
    print(f"  {'Position':<10} {'Years':>6} {'Avg Corr':>10} {'Min':>8} {'Max':>8} {'Status':>8}")
    print(f"  {'-'*10} {'-'*6} {'-'*10} {'-'*8} {'-'*8} {'-'*8}")

    positions = ['QB', 'RB', 'WR', 'TE', 'DB', 'LB', 'EDGE', 'DL']
    for pos in positions:
        pos_results = [r for r in all_results if r['position'] == pos]
        if not pos_results:
            continue
        corrs = [r['correlation'] for r in pos_results]
        avg_c = sum(corrs) / len(corrs)
        status = 'WEAK' if avg_c < 0.6 else '✓'
        print(f"  {pos:<10} {len(corrs):>6} {avg_c:>10.3f} {min(corrs):>8.3f} {max(corrs):>8.3f} {status:>8}")


if __name__ == '__main__':
    import sys
    if '--validate' in sys.argv:
        validate_weights()
    else:
        from clean import run as clean_run
        _, df_transfers = clean_run()
        df_transfers, df_scored = compute_success_delta(df_transfers)
        compute_success_factor(df_scored)
        print("\nFeature engineering complete.")
