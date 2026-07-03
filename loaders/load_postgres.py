"""
load_postgres.py â€” Load Toronto OSM graph into PostgreSQL with pgRouting.
Usage: python loaders/load_postgres.py
"""

import sys
import yaml
import osmnx as ox
import psycopg2
import psycopg2.extras
import numpy as np
from pathlib import Path
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"
GRAPH_PATH = BASE_DIR / "data" / "toronto_graph.graphml"


def load_config():
    """Load database and experiment configuration from settings.yaml.
    
    Returns:
        dict: Configuration dictionary with postgres, neo4j, toronto, and experiment keys.
    Raises:
        FileNotFoundError: If settings.yaml is not found at the expected path.
    """
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_connection(cfg):
    """Create and return a psycopg2 connection using config settings.
    
    Args:
        cfg (dict): Configuration dictionary with postgres connection details.
    Returns:
        psycopg2.connection: Active database connection.
    """
    pg = cfg["postgres"]
    return psycopg2.connect(
        host=pg["host"], port=pg["port"],
        dbname=pg["database"], user=pg["user"], password=pg["password"]
    )


def load_graph():
    if not GRAPH_PATH.exists():
        print(f"ERROR: {GRAPH_PATH} not found. Run download_data.py first.")
        sys.exit(1)
    print("[PG] Loading graph from disk...")
    G = ox.load_graphml(GRAPH_PATH)
    nodes, edges = ox.graph_to_gdfs(G)
    return G, nodes, edges


def insert_nodes(conn, nodes):
    print(f"[PG] Inserting {len(nodes):,} nodes...")
    cur = conn.cursor()
    cur.execute("TRUNCATE road_nodes CASCADE;")

    records = []
    for osm_id, row in tqdm(nodes.iterrows(), total=len(nodes), desc="Nodes"):
        records.append((
            int(osm_id),
            float(row.geometry.x),
            float(row.geometry.y),
            f"SRID=4326;POINT({row.geometry.x} {row.geometry.y})"
        ))
        if len(records) >= 5000:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO road_nodes (osm_id, lon, lat, geom) VALUES %s "
                "ON CONFLICT DO NOTHING",
                records,
                template="(%s, %s, %s, ST_GeomFromEWKT(%s))"
            )
            records = []

    if records:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO road_nodes (osm_id, lon, lat, geom) VALUES %s "
            "ON CONFLICT DO NOTHING",
            records,
            template="(%s, %s, %s, ST_GeomFromEWKT(%s))"
        )
    conn.commit()
    cur.close()
    print(f"[PG] Nodes inserted.")


def insert_edges(conn, edges, nodes):
    print(f"[PG] Inserting {len(edges):,} edges...")
    cur = conn.cursor()
    cur.execute("TRUNCATE road_edges CASCADE;")

    # Build osm_id â†’ db_id mapping
    cur.execute("SELECT osm_id, id FROM road_nodes;")
    node_map = {row[0]: row[1] for row in cur.fetchall()}

    records = []
    for (u, v, key), row in tqdm(edges.iterrows(), total=len(edges), desc="Edges"):
        src_id = node_map.get(int(u))
        tgt_id = node_map.get(int(v))
        if src_id is None or tgt_id is None:
            continue

        travel_time = float(row.get("travel_time", row.get("length", 1.0) / 13.9))
        length_m = float(row.get("length", 0.0))
        highway = str(row.get("highway", ""))[:50] if row.get("highway") else None
        name = str(row.get("name", ""))[:200] if row.get("name") else None

        geom_wkt = f"SRID=4326;{row.geometry.wkt}" if row.geometry else None

        records.append((
            int(u), src_id, tgt_id, travel_time, travel_time,
            length_m, highway, name, geom_wkt
        ))

        if len(records) >= 5000:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO road_edges
                   (osm_id, source, target, cost, reverse_cost, length_m, highway, name, geom)
                   VALUES %s""",
                records,
                template="(%s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromEWKT(%s))"
            )
            records = []

    if records:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO road_edges
               (osm_id, source, target, cost, reverse_cost, length_m, highway, name, geom)
               VALUES %s""",
            records,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromEWKT(%s))"
        )

    conn.commit()
    cur.close()

    # Verify with pgRouting topology
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM road_edges;")
    count = cur.fetchone()[0]
    cur.close()
    print(f"[PG] Edges inserted: {count:,} rows in road_edges.")


def create_indexes(conn):
    print("[PG] Creating additional indexes for pgRouting...")
    cur = conn.cursor()
    cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_cost ON road_edges(cost);")
    cur.execute("ANALYZE road_edges;")
    cur.execute("ANALYZE road_nodes;")
    conn.commit()
    cur.close()
    print("[PG] Indexes and ANALYZE complete.")


def main():
    cfg = load_config()
    print("=" * 60)
    print("  Urban Routing Benchmark â€” PostgreSQL Loader")
    print("=" * 60)

    conn = get_connection(cfg)
    print(f"[PG] Connected to PostgreSQL at {cfg['postgres']['host']}:{cfg['postgres']['port']}")

    G, nodes, edges = load_graph()
    insert_nodes(conn, nodes)
    insert_edges(conn, edges, nodes)
    create_indexes(conn)
    conn.close()

    print("\n[DONE] PostgreSQL loaded successfully.")
    print("Next step: python loaders/load_neo4j.py")


if __name__ == "__main__":
    main()
