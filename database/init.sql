-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create detections table
CREATE TABLE IF NOT EXISTS detections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id VARCHAR(255) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    detected BOOLEAN NOT NULL DEFAULT FALSE,
    confidence FLOAT NOT NULL,
    threshold FLOAT NOT NULL,
    processing_time_ms FLOAT NOT NULL,
    picks TEXT,
    metadata TEXT,
    agreement BOOLEAN,
    confidence_diff FLOAT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('detections', 'created_at', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_detections_event_id ON detections(event_id);
CREATE INDEX IF NOT EXISTS idx_detections_model_name ON detections(model_name);
CREATE INDEX IF NOT EXISTS idx_detections_created_at ON detections(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_detections_detected ON detections(detected);
CREATE INDEX IF NOT EXISTS idx_detections_agreement ON detections(agreement);
CREATE INDEX IF NOT EXISTS idx_detections_event_model ON detections(event_id, model_name);
CREATE INDEX IF NOT EXISTS idx_detections_created_detected ON detections(created_at, detected);

-- Create continuous aggregate for hourly statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS detection_stats_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', created_at) AS bucket,
    model_name,
    COUNT(*) as total_detections,
    SUM(CASE WHEN detected THEN 1 ELSE 0 END) as positive_detections,
    AVG(confidence) as avg_confidence,
    AVG(processing_time_ms) as avg_processing_time
FROM detections
GROUP BY bucket, model_name
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('detection_stats_hourly',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Create retention policy (optional - keeps data for 90 days)
-- SELECT add_retention_policy('detections', INTERVAL '90 days', if_not_exists => TRUE);