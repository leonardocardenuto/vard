import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from api.services.camera_streams import ensure_camera_stream, _stream_processes


class CameraStreamTests(TestCase):
    def test_missing_ffmpeg_has_a_clear_error_instead_of_an_unhandled_exception(self):
        camera = SimpleNamespace(id=uuid.uuid4(), stream_url="rtsp://camera.test/live", connection_type="rtsp")
        with tempfile.TemporaryDirectory() as directory, patch("api.services.camera_streams.STREAMS_ROOT", Path(directory)), patch(
            "api.services.camera_streams.subprocess.Popen", side_effect=FileNotFoundError("ffmpeg")
        ):
            with self.assertRaisesRegex(RuntimeError, "FFmpeg não está instalado"):
                ensure_camera_stream(camera, timeout_seconds=0)
        self.assertNotIn(camera.id, _stream_processes)
