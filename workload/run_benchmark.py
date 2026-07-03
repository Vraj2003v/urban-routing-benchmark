"""
run_benchmark.py â€” Main benchmark orchestrator.
Runs concurrent routing queries and edge-weight updates against Neo4j and PostgreSQL,
measures latency, and writes results to CSV.

Usage:
    python workload/run_benchmark.py [options]

Options:
    --duration      Benchmark duration in seconds (default: 300)
    --update-freq   Edge-weight updates per second (default: 1.0)
    --query-rate    Routing queries per second per system (default: 5)
    --workers       Parallel worker threads (default: 4)
    --pattern       Update pattern: random | sinusoidal | spike (default: random)
                    Ignored when --live is set.
    --live          Use real-time data (GTFS-RT, 511 Ontario, HERE) for edge updates
    --here-key      HERE Traffic Flow API key (optional, used with --live)
    --output        Output CSV path (default: results/run_001.csv)
"""

import argparse
import csv
import sys
import time
import threading
import queue
import random
import hashlib
import yaml
import psycopg2
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
TORONTO_TZ = ZoneInfo("America/Toronto")
from neo4j import GraphDatabase

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from workload.query_generator import QueryGenerator
from workload.update_generator import UpdateGenerator

CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"
RESULTS_DIR = BASE_DIR / "results"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def parse_args():
    cfg = load_config()
    exp = cfg["experiment"]
    p = argparse.ArgumentParser(description="Urban Routing Benchmark")
    p.add_argument("--duration",    type=int,   default=exp["default_duration_sec"])
    p.add_argument("--update-freq", type=float, default=exp["default_update_freq_hz"])
    p.add_argument("--query-rate",  type=float, default=exp["default_query_rate_hz"])
    p.add_argument("--workers",     type=int,   default=exp["default_workers"])
    p.add_argument("--pattern",     type=str,   default="random",
                   choices=["random", "sinusoidal", "spike"])
    p.add_argument("--live",        action="store_true",
                   help="Derive edge-weight updates from live GTFS-RT / 511-ON / HERE data")
    p.add_argument("--here-key",    type=str,   default="",
                   help="HERE Traffic Flow API key (optional, used with --live)")
    p.add_argument("--output",      type=str,   default=str(RESULTS_DIR / "run_001.csv"))
    return p.parse_args(), cfg


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PostgreSQL worker
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def pg_worker(cfg, query_gen, result_queue, stop_event, query_interval_sec):
    pg = cfg["postgres"]
    conn = psycopg2.connect(
        host=pg["host"], port=pg["port"],
        dbname=pg["database"], user=pg["user"], password=pg["password"]
    )
    conn.autocommit = True
    cur = conn.cursor()

    while not stop_event.is_set():
        t_start = time.perf_counter()
        src, tgt = query_gen.next_pair()

        try:
            cur.execute("EXPLAIN (FORMAT JSON, ANALYZE, BUFFERS) " +
                query_gen.postgres_dijkstra_query(src, tgt))
            plan_json = cur.fetchall()

            cur.execute(query_gen.postgres_dijkstra_query(src, tgt))
            rows = cur.fetchall()
            latency = time.perf_counter() - t_start

            plan_hash = hashlib.md5(str(plan_json).encode()).hexdigest()[:8]

            result_queue.put({
                "ts": datetime.now(TORONTO_TZ).isoformat(),
                "system": "postgres",
                "src": src,
                "tgt": tgt,
                "latency_ms": round(latency * 1000, 3),
                "result_rows": len(rows),
                "plan_hash": plan_hash,
                "error": ""
            })
        except Exception as e:
            result_queue.put({
                "ts": datetime.now(TORONTO_TZ).isoformat(),
                "system": "postgres",
                "src": src, "tgt": tgt,
                "latency_ms": -1,
                "result_rows": 0,
                "plan_hash": "",
                "error": str(e)[:200]
            })

        time.sleep(max(0, query_interval_sec - (time.perf_counter() - t_start)))

    cur.close()
    conn.close()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Neo4j worker
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def neo4j_worker(cfg, query_gen, node_map, result_queue, stop_event, query_interval_sec):
    driver = GraphDatabase.driver(
        cfg["neo4j"]["uri"],
        auth=(cfg["neo4j"]["user"], cfg["neo4j"]["password"])
    )

    with driver.session() as session:
        while not stop_event.is_set():
            t_start = time.perf_counter()
            src_db, tgt_db = query_gen.next_pair()
            src_osm = node_map.get(src_db, src_db)
            tgt_osm = node_map.get(tgt_db, tgt_db)

            try:
                result = session.run(
                    """
                    MATCH (src:Intersection {osm_id: $src}),
                          (tgt:Intersection {osm_id: $tgt})
                    CALL apoc.algo.dijkstra(src, tgt, 'ROAD>', 'cost')
                    YIELD path, weight
                    RETURN weight AS total_cost, length(path) AS hops
                    LIMIT 1
                    """,
                    src=src_osm, tgt=tgt_osm
                )
                rows = result.data()
                latency = time.perf_counter() - t_start

                result_queue.put({
                    "ts": datetime.now(TORONTO_TZ).isoformat(),
                    "system": "neo4j",
                    "src": src_osm,
                    "tgt": tgt_osm,
                    "latency_ms": round(latency * 1000, 3),
                    "result_rows": len(rows),
                    "plan_hash": "n4j_apoc",
                    "error": ""
                })
            except Exception as e:
                result_queue.put({
                    "ts": datetime.now(TORONTO_TZ).isoformat(),
                    "system": "neo4j",
                    "src": src_osm, "tgt": tgt_osm,
                    "latency_ms": -1,
                    "result_rows": 0,
                    "plan_hash": "",
                    "error": str(e)[:200]
                })

            time.sleep(max(0, query_interval_sec - (time.perf_counter() - t_start)))

    driver.close()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Update worker
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def update_worker(cfg, update_gen, stop_event, update_interval_sec, stats):
    pg = cfg["postgres"]
    conn = psycopg2.connect(
        host=pg["host"], port=pg["port"],
        dbname=pg["database"], user=pg["user"], password=pg["password"]
    )
    driver = GraphDatabase.driver(
        cfg["neo4j"]["uri"],
        auth=(cfg["neo4j"]["user"], cfg["neo4j"]["password"])
    )

    with driver.session() as session:
        while not stop_event.is_set():
            t = time.perf_counter()
            updates = update_gen.generate_batch(batch_size=50)
            update_gen.apply_to_postgres(conn, updates)
            update_gen.apply_to_neo4j(session, updates)
            stats["updates"] += len(updates)
            elapsed = time.perf_counter() - t
            time.sleep(max(0, update_interval_sec - elapsed))

    conn.close()
    driver.close()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CSV writer
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def csv_writer(result_queue, output_path, stop_event):
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "ts", "system", "src", "tgt",
            "latency_ms", "result_rows", "plan_hash", "error"
        ])
        writer.writeheader()
        while not stop_event.is_set() or not result_queue.empty():
            try:
                row = result_queue.get(timeout=0.5)
                writer.writerow(row)
                f.flush()
            except queue.Empty:
                continue


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Node map: db_id â†’ osm_id
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def build_node_map(cfg):
    pg = cfg["postgres"]
    conn = psycopg2.connect(
        host=pg["host"], port=pg["port"],
        dbname=pg["database"], user=pg["user"], password=pg["password"]
    )
    cur = conn.cursor()
    cur.execute("SELECT id, osm_id FROM road_nodes LIMIT 50000")
    m = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return m


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Main
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main():
    args, cfg = parse_args()

    # Inject HERE key into config if provided via CLI
    if args.here_key:
        cfg.setdefault("here", {})["api_key"] = args.here_key

    mode = "live" if args.live else "synthetic"

    print("=" * 60)
    print("  Urban Routing Benchmark â€” Run")
    print(f"  Duration:    {args.duration}s")
    print(f"  Update freq: {args.update_freq} Hz  |  Mode: {mode.upper()}")
    if mode == "live":
        print("  Live sources: GTFS-RT (TTC), 511 Ontario" +
              (", HERE Traffic" if args.here_key else " [HERE disabled â€” no API key]"))
    else:
        print(f"  Pattern:     {args.pattern}")
    print(f"  Query rate:  {args.query_rate} Hz per system")
    print(f"  Workers:     {args.workers}")
    print(f"  Output:      {args.output}")
    print("=" * 60)

    query_gen = QueryGenerator(cfg)
    update_gen = UpdateGenerator(cfg, pattern=args.pattern, mode=mode)
    node_map = build_node_map(cfg)

    result_queue = queue.Queue()
    stop_event = threading.Event()
    stats = {"updates": 0}

    query_interval = 1.0 / args.query_rate
    update_interval = 1.0 / args.update_freq

    threads = []

    # Warm-up notice
    warm_up = cfg["experiment"]["warm_up_sec"]
    print(f"\n[Benchmark] Warming up for {warm_up}s (queries run but not recorded)...")
    time.sleep(warm_up)

    # Start PostgreSQL query workers
    for _ in range(max(1, args.workers // 2)):
        t = threading.Thread(
            target=pg_worker,
            args=(cfg, query_gen, result_queue, stop_event, query_interval),
            daemon=True
        )
        t.start()
        threads.append(t)

    # Start Neo4j query workers
    for _ in range(max(1, args.workers // 2)):
        t = threading.Thread(
            target=neo4j_worker,
            args=(cfg, query_gen, node_map, result_queue, stop_event, query_interval),
            daemon=True
        )
        t.start()
        threads.append(t)

    # Start update worker
    t = threading.Thread(
        target=update_worker,
        args=(cfg, update_gen, stop_event, update_interval, stats),
        daemon=True
    )
    t.start()
    threads.append(t)

    # Start CSV writer
    t = threading.Thread(
        target=csv_writer,
        args=(result_queue, args.output, stop_event),
        daemon=True
    )
    t.start()
    threads.append(t)

    print(f"[Benchmark] Running for {args.duration}s... (Ctrl+C to stop early)")

    t_start = time.time()
    try:
        while time.time() - t_start < args.duration:
            elapsed = int(time.time() - t_start)
            print(f"\r  Elapsed: {elapsed:>4}s / {args.duration}s   "
                  f"Updates applied: {stats['updates']:>6}   "
                  f"Results queued: {result_queue.qsize():>5}", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Benchmark] Interrupted by user.")

    print("\n[Benchmark] Stopping workers...")
    stop_event.set()
    for t in threads:
        t.join(timeout=5)

    print(f"\n[DONE] Results written to: {args.output}")
    print(f"       Total edge updates applied: {stats['updates']:,}")
    update_gen.stop()
    print("\nNext step: python analysis/capture_plans.py --input " + args.output)


if __name__ == "__main__":
    main()
