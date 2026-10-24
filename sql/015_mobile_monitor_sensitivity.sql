-- Keep the agreed 2.0 g sensitivity when upgrading the original defaults.
-- Preserve any explicitly customized impact threshold.
UPDATE mobile_monitor_settings
SET parameters = jsonb_set(parameters, '{impact_g}', '2.0'::jsonb)
WHERE id = 1 AND parameters -> 'impact_g' = '2.5'::jsonb;
