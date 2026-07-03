"""
capture_plans.py — Analyze benchmark results: plan regression, latency stats, index usage.
Usage: python analysis/capture_plans.py --input results/run_001.csv
"""

import argparse
import sys
import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from analysis.regression_detector import detect_regressions, plan_cache_hit_rate

RESULTS_DIR = BASE_DIR / "results"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Path to benchmark CSV")
    return p.parse_args()


def load_results(path):
    df = pd.read_csv(path, parse_dates=["ts"])
    df = df[df["latency_ms"] > 0]  # drop errored queries
    print(f"[Analysis] Loaded {len(df):,} valid query results from {path}")
    return df


def latency_summary(df):
    print("\n" + "=" * 60)
    print("  LATENCY SUMMARY (ms)")
    print("=" * 60)
    for system in ["postgres", "neo4j"]:
        sub = df[df["system"] == system]["latency_ms"]
        if sub.empty:
            print(f"  {system}: no data")
            continue
        print(f"\n  {system.upper()}")
        print(f"    Count  : {len(sub):,}")
        print(f"    Mean   : {sub.mean():.2f} ms")
        print(f"    Median : {sub.median():.2f} ms")
        print(f"    P95    : {sub.quantile(0.95):.2f} ms")
        print(f"    P99    : {sub.quantile(0.99):.2f} ms")
        print(f"    Std    : {sub.std():.2f} ms")
        print(f"    Max    : {sub.max():.2f} ms")


def plan_analysis(df):
    print("\n" + "=" * 60)
    print("  QUERY PLAN ANALYSIS")
    print("=" * 60)
    for system in ["postgres", "neo4j"]:
        sub = df[df["system"] == system]
        if sub.empty:
            continue
        unique_plans = sub["plan_hash"].nunique()
        hit_rate = plan_cache_hit_rate(df, system)
        print(f"\n  {system.upper()}")
        print(f"    Unique plan hashes : {unique_plans}")
        print(f"    Plan cache hit rate: {hit_rate:.1%}")

        regressions = detect_regressions(df, system)
        print(f"    Regression events  : {len(regressions)}")
        if not regressions.empty:
            print(f"    Avg regression ratio: {regressions['ratio'].mean():.2f}x latency increase")


def write_report(df, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # Plan analysis CSV
    plan_rows = []
    for system in ["postgres", "neo4j"]:
        regressions = detect_regressions(df, system)
        for _, r in regressions.iterrows():
            plan_rows.append(r.to_dict())

    plan_df = pd.DataFrame(plan_rows)
    plan_path = output_dir / "plan_analysis.csv"
    plan_df.to_csv(plan_path, index=False)
    print(f"\n[Analysis] Plan regression CSV → {plan_path}")

    # Full regression report text
    report_path = output_dir / "regression_report.txt"
    with open(report_path, "w") as f:
        f.write("Urban Routing Benchmark — Regression Report\n")
        f.write("=" * 60 + "\n\n")
        for system in ["postgres", "neo4j"]:
            sub = df[df["system"] == system]["latency_ms"]
            f.write(f"{system.upper()}\n")
            if sub.empty:
                f.write("  No data.\n\n")
                continue
            f.write(f"  Queries   : {len(sub):,}\n")
            f.write(f"  Mean (ms) : {sub.mean():.2f}\n")
            f.write(f"  P95 (ms)  : {sub.quantile(0.95):.2f}\n")
            f.write(f"  P99 (ms)  : {sub.quantile(0.99):.2f}\n")
            hit_rate = plan_cache_hit_rate(df, system)
            f.write(f"  Plan hit% : {hit_rate:.1%}\n")
            regressions = detect_regressions(df, system)
            f.write(f"  Regressions: {len(regressions)}\n")
            if not regressions.empty:
                f.write(f"  Avg ratio  : {regressions['ratio'].mean():.2f}x\n")
            f.write("\n")

    print(f"[Analysis] Text report → {report_path}")


def main():
    args = parse_args()
    df = load_results(args.input)
    latency_summary(df)
    plan_analysis(df)
    write_report(df, RESULTS_DIR)
    print("\n[DONE] Analysis complete.")
    print("Next step: python dashboard/app.py  →  http://localhost:8050")


if __name__ == "__main__":
    main()
