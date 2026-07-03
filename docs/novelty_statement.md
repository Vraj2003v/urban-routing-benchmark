# Novelty Statement — Group 9

## What is Novel About This Study

1. Plan Cache Instability Quantified: PostgreSQL produces 753-1928 unique query plan hashes per benchmark run under dynamic edge-weight updates, against Neo4j's single stable execution plan. This is the first systematic quantification of this instability at update frequencies between 0.1 Hz and 10 Hz on a real urban road network.

2. Real Canadian Open Data Integration: The benchmark uses live TTC GTFS-Realtime and 511 Ontario incident feeds as weight drivers, grounding the synthetic workload in real traffic conditions specific to Toronto.

3. Cross-System Regression Detection: A unified plan-regression detector operates across both PostgreSQL (EXPLAIN ANALYZE) and Neo4j (PROFILE), enabling direct comparison of optimizer behaviour under identical workloads.

4. Update Frequency as Independent Variable: Systematically varying update frequency (0.1, 1.0, 5.0, 10.0 Hz) across random, sinusoidal, and spike patterns isolates the effect of update rate on query plan stability.
