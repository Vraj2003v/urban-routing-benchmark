CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS road_edges (
    id           BIGSERIAL PRIMARY KEY,
    osm_id       BIGINT,
    source       BIGINT,
    target       BIGINT,
    cost         FLOAT,
    reverse_cost FLOAT,
    length_m     FLOAT,
    highway      TEXT,
    name         TEXT,
    geom         GEOMETRY(LINESTRING, 4326)
);

CREATE TABLE IF NOT EXISTS road_nodes (
    id      BIGSERIAL PRIMARY KEY,
    osm_id  BIGINT,
    lon     FLOAT,
    lat     FLOAT,
    geom    GEOMETRY(POINT, 4326)
);

CREATE TABLE IF NOT EXISTS edge_weight_log (
    id         BIGSERIAL PRIMARY KEY,
    edge_id    BIGINT,
    old_cost   FLOAT,
    new_cost   FLOAT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_road_edges_source ON road_edges(source);
CREATE INDEX IF NOT EXISTS idx_road_edges_target ON road_edges(target);
CREATE INDEX IF NOT EXISTS idx_road_edges_geom   ON road_edges USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_road_nodes_geom   ON road_nodes USING GIST(geom);
