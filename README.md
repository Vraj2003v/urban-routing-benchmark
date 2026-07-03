# Urban Routing Benchmark â€” COMP.8157 Group 9
**Dynamic Edge-Weight Query Processing: Neo4j vs PostgreSQL/pgRouting**

---

## Project Overview

This benchmark compares Neo4j (GDBMS) and PostgreSQL with pgRouting (RDBMS) under
dynamic, high-frequency edge-weight updates on a real Toronto urban road network.

**Components:**
- `loaders/`   â€” OSM + GTFS data download and database loading
- `workload/`  â€” Mixed routing query + edge-weight update generator
- `analysis/`  â€” Query plan capture, latency measurement, regression detection
- `dashboard/` â€” Web dashboard to visualize results
- `results/`   â€” CSV output from benchmark runs
- `config/`    â€” Database connection and experiment configuration

---


## Related Work

This study builds on literature spanning graph database performance, pgRouting benchmarking, dynamic edge-weight routing, and query plan stability. Graph-native engines outperform relational systems on traversal-heavy queries via index-free adjacency, while pgRouting exhibits plan instability under frequent cost updates. Our study extends this by quantifying plan-cache hit rates across five update-frequency tiers on a real Toronto road network with live Canadian open data feeds.


## Related Work

This study builds on literature spanning graph database performance, pgRouting benchmarking, dynamic edge-weight routing, and query plan stability. Graph-native engines outperform relational systems on traversal-heavy queries via index-free adjacency, while pgRouting exhibits plan instability under frequent cost updates. Our study extends this by quantifying plan-cache hit rates across five update-frequency tiers on a real Toronto road network with live Canadian open data feeds.

## Prerequisites

### System Requirements
- Python 3.10+
- Docker + Docker Compose (for Neo4j and PostgreSQL)
- 8 GB RAM minimum (16 GB recommended for Toronto dataset)
- 10 GB free disk space

### Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Start Databases (Docker)
```bash
docker-compose up -d
```
Wait ~30 seconds for both databases to be ready, then verify:
```bash
docker-compose ps
```

---

## Step-by-Step: How to Run

### Step 1 â€” Download Toronto OSM + GTFS Data
```bash
python loaders/download_data.py
```
Downloads:
- Toronto road network from OpenStreetMap (Overpass API)
- TTC GTFS transit feed (Toronto open data)

Output: `data/toronto.osm.pbf`, `data/gtfs/`

---

### Step 2 â€” Load Data into Both Databases
```bash
# Load into PostgreSQL + pgRouting
python loaders/load_postgres.py

# Load into Neo4j
python loaders/load_neo4j.py
```
Both scripts print progress and row counts when done.

---

### Step 3 â€” Run the Benchmark
```bash
python workload/run_benchmark.py --duration 300 --update-freq 1.0
```

**Key options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--duration` | 300 | Benchmark duration in seconds |
| `--update-freq` | 1.0 | Edge-weight updates per second |
| `--query-rate` | 5 | Routing queries per second |
| `--workers` | 4 | Parallel worker threads |
| `--output` | results/run_001.csv | Output CSV path |

**Example â€” simulate peak-hour high-frequency updates:**
```bash
python workload/run_benchmark.py --duration 600 --update-freq 10.0 --query-rate 10 --output results/peak_hour.csv
```

**Example â€” low-frequency baseline:**
```bash
python workload/run_benchmark.py --duration 300 --update-freq 0.1 --query-rate 5 --output results/baseline.csv
```

---

### Step 4 â€” Capture and Analyze Query Plans
```bash
python analysis/capture_plans.py --input results/run_001.csv
```
Detects plan regression events and writes:
- `results/plan_analysis.csv` â€” per-query plan hashes and latency
- `results/regression_report.txt` â€” human-readable summary

---

### Step 5 â€” View the Dashboard
```bash
python dashboard/app.py
```
Open your browser at: **http://localhost:8050**

The dashboard shows:
- Latency over time (Neo4j vs PostgreSQL)
- Plan cache hit rate over time
- Regression event markers
- Update frequency vs. latency correlation

---

## Configuration

Edit `config/settings.yaml` to change database credentials, ports, or experiment parameters.

```yaml
postgres:
  host: localhost
  port: 5432
  database: routing_bench
  user: bench
  password: bench123

neo4j:
  uri: bolt://localhost:7687
  user: neo4j
  password: bench123

toronto:
  osm_area_id: 3444656  # Toronto relation ID on OpenStreetMap
  gtfs_url: "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/ttc-routes-and-schedules/resource/ca43ac3d-3940-4315-889b-a768f670c1f6/download/TTC_Routes_and_Schedules_Data.zip"
```

---

## Output Files

| File | Description |
|------|-------------|
| `results/run_*.csv` | Raw latency measurements per query |
| `results/plan_analysis.csv` | Query plan hashes, regression flags |
| `results/regression_report.txt` | Summary statistics |
| `results/figures/` | Auto-generated plots (PNG) |

---

## Troubleshooting

**Databases not ready:**
```bash
docker-compose logs neo4j
docker-compose logs postgres
```

**pgRouting extension missing:**
```bash
docker exec -it urban_routing_postgres psql -U bench -d routing_bench -c "CREATE EXTENSION pgrouting;"
```

**Neo4j connection refused:**
Check that port 7687 is not in use by another service. Edit `config/settings.yaml` to change the port.

**OSM download slow:**
Toronto's OSM data is ~200 MB. Use the pre-clipped PBF from Geofabrik instead:
```bash
wget https://download.geofabrik.de/north-america/canada/ontario-latest.osm.pbf -O data/toronto.osm.pbf
```
Then set `use_geofabrik: true` in `config/settings.yaml`.

---

## Project Structure

```
urban_routing_benchmark/
â”œâ”€â”€ README.md
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ docker-compose.yml
â”œâ”€â”€ config/
â”‚   â””â”€â”€ settings.yaml
â”œâ”€â”€ loaders/
â”‚   â”œâ”€â”€ download_data.py
â”‚   â”œâ”€â”€ load_postgres.py
â”‚   â””â”€â”€ load_neo4j.py
â”œâ”€â”€ workload/
â”‚   â”œâ”€â”€ run_benchmark.py
â”‚   â”œâ”€â”€ query_generator.py
â”‚   â””â”€â”€ update_generator.py
â”œâ”€â”€ analysis/
â”‚   â”œâ”€â”€ capture_plans.py
â”‚   â””â”€â”€ regression_detector.py
â”œâ”€â”€ dashboard/
â”‚   â””â”€â”€ app.py
â”œâ”€â”€ data/         (created at runtime)
â””â”€â”€ results/      (created at runtime)
```

---

## Authors
Group 9 â€” COMP.8157 Advanced Database Topics, University of Windsor, 2026S

---

## Live Data Mode

The benchmark supports **real-time data** from three sources, which replace the synthetic
congestion patterns with actual current traffic conditions.

### Available Live Sources

| Source | What it provides | API key? |
|--------|-----------------|----------|
| **TTC GTFS-Realtime** | Live bus/streetcar delays per route | None required |
| **511 Ontario** | Road incidents, closures, construction | None required |
| **HERE Traffic Flow** | Per-segment live speed & travel time | Free key required |

### Step 1 â€” Download Static + Live Data

```bash
# Static only (original behaviour):
python loaders/download_data.py

# Static + live snapshot:
python loaders/download_data.py --live

# Static + live + HERE Traffic (requires API key):
python loaders/download_data.py --live --here-key YOUR_HERE_API_KEY
```

Get a free HERE API key at: https://developer.here.com/ (250,000 requests/month free)

### Step 2 â€” Run Benchmark in Live Mode

```bash
# Live mode â€” edge weights updated from real GTFS-RT + 511 data:
python workload/run_benchmark.py --live --duration 300 --update-freq 1.0

# Live mode with HERE Traffic speeds:
python workload/run_benchmark.py --live --here-key YOUR_HERE_API_KEY --duration 300

# Synthetic mode is still available (default):
python workload/run_benchmark.py --pattern sinusoidal --duration 300
```

### How Live Updates Work

```
Every 60 seconds (background thread):
  1. Fetch TTC TripUpdates from GTFS-RT protobuf feed
     â†’ parse per-route average delay in seconds
  2. Fetch 511 Ontario incidents (lat/lon + severity)
  3. Fetch HERE Traffic speeds per road segment (if key provided)

For each edge-weight update batch:
  - For each sampled edge (lat/lon from geometry centroid):
      multiplier = incident_proximity_factor(511 data)
                 Ã— speed_ratio_factor(HERE data)
                 Ã— small_noise(Â±5%)
  - new_cost = base_cost Ã— multiplier
  - Apply to both PostgreSQL and Neo4j simultaneously
```

### Reproducibility with Live Data

Every live data fetch is automatically saved as a timestamped JSON snapshot:

```
data/live_snapshots/snapshot_20260529T143022Z.json
```

These snapshots let you replay the exact same live conditions later, or include
them as supplementary material in your report.

### Adding Live Data Config

Edit `config/settings.yaml` to set your HERE API key permanently:

```yaml
here:
  api_key: "YOUR_HERE_API_KEY_HERE"
```

Or set custom feed URLs if using a different city's GTFS-RT provider.

