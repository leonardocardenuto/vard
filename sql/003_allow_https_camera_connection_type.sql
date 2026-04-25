BEGIN;

ALTER TABLE cameras
DROP CONSTRAINT IF EXISTS cameras_connection_type_check;

ALTER TABLE cameras
ADD CONSTRAINT cameras_connection_type_check
CHECK (connection_type IN ('rtsp', 'https', 'onvif', 'hls', 'webrtc', 'other'));

COMMIT;
