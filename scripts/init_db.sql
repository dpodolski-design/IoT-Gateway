-- IoT Gateway prototype: devices, rules, event_logs

CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL UNIQUE,
    type VARCHAR(64) NOT NULL CHECK (type IN ('speaker', 'sensor_smoke')),
    msisdn VARCHAR(32),
    subscriber_id VARCHAR(255),
    vendor VARCHAR(128),
    endpoint VARCHAR(512),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_devices_msisdn ON devices(msisdn);
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(type);

CREATE TABLE IF NOT EXISTS rules (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    action_type VARCHAR(64) NOT NULL DEFAULT 'call',
    target VARCHAR(64) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rules_event_device ON rules(event_type, device_id);

CREATE TABLE IF NOT EXISTS event_logs (
    id SERIAL PRIMARY KEY,
    event_kind VARCHAR(64) NOT NULL,
    device_id VARCHAR(255),
    rule_id INTEGER,
    call_id VARCHAR(255),
    target_number VARCHAR(64),
    result VARCHAR(32) NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_logs_created ON event_logs(created_at DESC);
