"""
load_neo4j.py â€” Load Toronto OSM graph into Neo4j.
Usage: python loaders/load_neo4j.py
"""

import sys
import yaml
import osmnx as ox
from neo4j import GraphDatabase
from pathlib import Path
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"
GRAPH_PATH = BASE_DIR / "data" / "toronto_graph.graphml"

BATCH_SIZE = 1000


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_driver(cfg):
    n4j = cfg["neo4j"]
    return GraphDatabase.driver(n4j["uri"], auth=(n4j["user"], n4j["password"]))


def clear_database(session):
    """Clear all existing nodes and relationships from Neo4j before loading.
    
    This ensures a clean state before ingesting the Toronto road network.
    Called once at the start of each load operation.
    """
    print("[N4J] Clearing existing graph data...")
    session.run("MATCH (n) DETACH DELETE n")
    print("[N4J] Database cleared.")


def create_constraints(session):
    print("[N4J] Creating constraints and indexes...")
    session.run("CREATE CONSTRAINT node_osm_id IF NOT EXISTS FOR (n:Intersection) REQUIRE n.osm_id IS UNIQUE")
    session.run("CREATE INDEX road_edge_id IF NOT EXISTS FOR ()-[r:ROAD]-() ON (r.edge_id)")
    print("[N4J] Constraints created.")


def load_nodes(session, nodes):
    print(f"[N4J] Inserting {len(nodes):,} nodes...")
    node_list = []
    for osm_id, row in nodes.iterrows():
        node_list.append({
            "osm_id": int(osm_id),
            "lon": float(row.geometry.x),
            "lat": float(row.geometry.y)
        })

    for i in tqdm(range(0, len(node_list), BATCH_SIZE), desc="Nodes"):
        batch = node_list[i:i + BATCH_SIZE]
        session.run(
            """
            UNWIND $batch AS row
            MERGE (n:Intersection {osm_id: row.osm_id})
            SET n.lon = row.lon, n.lat = row.lat
            """,
            batch=batch
        )
    print(f"[N4J] Nodes inserted.")


def load_edges(session, edges):
    print(f"[N4J] Inserting {len(edges):,} edges...")
    edge_list = []
    edge_id = 0
    for (u, v, key), row in edges.iterrows():
        travel_time = float(row.get("travel_time", row.get("length", 1.0) / 13.9))
        length_m = float(row.get("length", 0.0))
        highway = str(row.get("highway", "")) if row.get("highway") else ""
        name = str(row.get("name", "")) if row.get("name") else ""

        edge_list.append({
            "edge_id": edge_id,
            "src": int(u),
            "tgt": int(v),
            "cost": round(travel_time, 4),
            "length_m": round(length_m, 2),
            "highway": highway[:100],
            "name": name[:200]
        })
        edge_id += 1

    for i in tqdm(range(0, len(edge_list), BATCH_SIZE), desc="Edges"):
        batch = edge_list[i:i + BATCH_SIZE]
        session.run(
            """
            UNWIND $batch AS row
            MATCH (src:Intersection {osm_id: row.src})
            MATCH (tgt:Intersection {osm_id: row.tgt})
            MERGE (src)-[r:ROAD {edge_id: row.edge_id}]->(tgt)
            SET r.cost     = row.cost,
                r.length_m = row.length_m,
                r.highway  = row.highway,
                r.name     = row.name
            """,
            batch=batch
        )
    print(f"[N4J] Edges inserted: {edge_id:,} relationships.")


def verify(session):
    result = session.run("MATCH (n:Intersection) RETURN count(n) AS cnt")
    node_count = result.single()["cnt"]
    result = session.run("MATCH ()-[r:ROAD]->() RETURN count(r) AS cnt")
    edge_count = result.single()["cnt"]
    print(f"[N4J] Verified: {node_count:,} nodes, {edge_count:,} edges in Neo4j.")


def main():
    cfg = load_config()
    print("=" * 60)
    print("  Urban Routing Benchmark â€” Neo4j Loader")
    print("=" * 60)

    if not GRAPH_PATH.exists():
        print(f"ERROR: {GRAPH_PATH} not found. Run download_data.py first.")
        sys.exit(1)

    print("[N4J] Loading graph from disk...")
    G = ox.load_graphml(GRAPH_PATH)
    nodes, edges = ox.graph_to_gdfs(G)
    print(f"[N4J] Graph loaded: {len(nodes):,} nodes, {len(edges):,} edges")

    driver = get_driver(cfg)
    print(f"[N4J] Connected to Neo4j at {cfg['neo4j']['uri']}")

    with driver.session() as session:
        clear_database(session)
        create_constraints(session)
        load_nodes(session, nodes)
        load_edges(session, edges)
        verify(session)

    driver.close()
    print("\n[DONE] Neo4j loaded successfully.")
    print("Next step: python workload/run_benchmark.py")


if __name__ == "__main__":
    main()
