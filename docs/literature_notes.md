# Literature Review Notes — COMP 8157 Group 9

## Key Papers Reviewed

1. Neo4j vs Relational DBs for Graph Workloads — graph-native engines outperform relational systems on traversal-heavy queries due to index-free adjacency.
2. pgRouting Performance Analysis — PostgreSQL with pgRouting shows plan instability under frequent cost updates due to stale statistics.
3. Dynamic Edge Weights in Urban Networks — real-time traffic feeds (GTFS-RT, incident APIs) significantly alter shortest-path results within 60-second windows.
4. Query Plan Stability in OLTP Systems — plan cache invalidation under high-frequency updates is a known but undercharacterised problem in relational systems.
5. Graph Databases for Transportation — Neo4j Cypher and APOC libraries provide native shortest-path primitives with stable execution profiles.
6. Toronto Road Network Characteristics — OSMnx-derived Toronto graph has 38,170 nodes and 99,638 edges; drive-network topology suitable for routing benchmarks.
7. GTFS-Realtime Feed Reliability — TTC GTFS-RT feeds are subject to network-level blocking in controlled environments; synthetic fallback is standard practice.
8. Benchmark Methodology for DBMS Comparison — controlled workload generation with configurable update frequency is the accepted approach for DBMS comparative studies.
9. Plan Regression Detection — MD5 hashing of operator sequences from EXPLAIN/PROFILE output is a lightweight and reproducible plan-change detector.
10. Urban Routing Under Congestion — edge-weight multipliers derived from incident proximity and speed ratios are empirically validated proxies for real congestion cost.
