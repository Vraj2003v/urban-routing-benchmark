"""
generate_demo_results.py — Generate synthetic benchmark results for dashboard testing.
Useful to test the dashboard BEFORE setting up Neo4j and PostgreSQL.

Usage: python generate_demo_results.py
"""

import csv
import random
import math
from datetime import datetime, timedelta
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)
OUTPUT = RESULTS_DIR / "demo_run.csv"

N_QUERIES = 3000
DURATION_SEC = 300
START = datetime(2026, 5, 15, 9, 0, 0)

plan_hashes_pg  = ["a1b2c3d4", "e5f6a7b8", "c9d0e1f2"]
plan_hashes_n4j = ["n4j_apoc"]

random.seed(42)

rows = []
for i in range(N_QUERIES):
    ts = START + timedelta(seconds=i * DURATION_SEC / N_QUERIES)
    elapsed_frac = i / N_QUERIES

    # Simulate sinusoidal congestion effect on latency
    congestion = 1.0 + 0.5 * math.sin(2 * math.pi * elapsed_frac * 3)

    # PostgreSQL: generally faster on simple queries, degrades under high update load
    pg_base = 45 + 20 * congestion + random.gauss(0, 8)
    pg_latency = max(5, pg_base)

    # Neo4j: higher baseline, more stable under updates
    n4j_base = 70 + 10 * congestion + random.gauss(0, 12)
    n4j_latency = max(8, n4j_base)

    # Simulate plan switches at 30% and 70% of the run for PG
    if elapsed_frac < 0.30:
        pg_plan = plan_hashes_pg[0]
    elif elapsed_frac < 0.70:
        pg_plan = plan_hashes_pg[1]
        pg_latency *= 1.6  # regression!
    else:
        pg_plan = plan_hashes_pg[2]

    src = random.randint(100000, 999999)
    tgt = random.randint(100000, 999999)

    rows.append({
        "ts": ts.isoformat(), "system": "postgres",
        "src": src, "tgt": tgt,
        "latency_ms": round(pg_latency, 3),
        "result_rows": random.randint(5, 80),
        "plan_hash": pg_plan, "error": ""
    })
    rows.append({
        "ts": ts.isoformat(), "system": "neo4j",
        "src": src, "tgt": tgt,
        "latency_ms": round(n4j_latency, 3),
        "result_rows": random.randint(5, 80),
        "plan_hash": plan_hashes_n4j[0], "error": ""
    })

with open(OUTPUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"[Demo] Generated {len(rows):,} synthetic result rows → {OUTPUT}")
print("       Run: python dashboard/app.py  →  http://localhost:8050")
print("       Select 'demo_run.csv' in the dashboard.")
