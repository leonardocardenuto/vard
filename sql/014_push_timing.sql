ALTER TABLE push_deliveries ADD COLUMN IF NOT EXISTS send_started_at timestamptz;
ALTER TABLE push_deliveries ADD COLUMN IF NOT EXISTS provider_duration_ms integer;
ALTER TABLE push_deliveries ADD COLUMN IF NOT EXISTS receipt_source text;
