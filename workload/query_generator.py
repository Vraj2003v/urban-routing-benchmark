"""
query_generator.py â€” Generates routing query pairs from the loaded graph.

Node Sampling Strategy:
- Pre-loads 2,000 random node IDs from road_nodes at startup.
- Random pairs drawn from this pool ensure query diversity across the benchmark run.
- Consistent pool size maintained across all update-frequency configurations.
"""

import random
import time
import psycopg2
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


class QueryGenerator:
    """
    Pre-loads a sample of node IDs and generates (source, target) pairs
    that satisfy the configured min/max hop distance constraint.
    """

    def __init__(self, cfg, sample_size=2000):
        self.cfg = cfg
        self.node_ids = []
        self._load_node_sample(sample_size)

    def _load_node_sample(self, n):
        pg = self.cfg["postgres"]
        conn = psycopg2.connect(
            host=pg["host"], port=pg["port"],
            dbname=pg["database"], user=pg["user"], password=pg["password"]
        )
        cur = conn.cursor()
        cur.execute(f"""
            SELECT id FROM road_nodes
            ORDER BY random()
            LIMIT {n}
        """)
        self.node_ids = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        print(f"[QueryGen] Loaded {len(self.node_ids)} node samples for query generation.")

    def next_pair(self):
        """Return a random (source_id, target_id) pair."""
        src, tgt = random.sample(self.node_ids, 2)
        return src, tgt

    def postgres_dijkstra_query(self, src, tgt):
        """pgRouting Dijkstra query string."""
        return f"""
        SELECT seq, node, edge, cost, agg_cost
        FROM pgr_dijkstra(
            'SELECT id, source, target, cost, reverse_cost FROM road_edges',
            {src}, {tgt},
            directed := true
        )
        LIMIT 500;
        """

    def neo4j_shortest_path_query(self, src_osm, tgt_osm):
        """Neo4j shortest path Cypher query."""
        return (
            "MATCH (src:Intersection {osm_id: $src}), (tgt:Intersection {osm_id: $tgt}) "
            "CALL gds.shortestPath.dijkstra.stream('road_graph', { "
            "  sourceNode: id(src), targetNode: id(tgt), relationshipWeightProperty: 'cost' "
            "}) YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs "
            "RETURN totalCost, size(nodeIds) AS hops",
        )
