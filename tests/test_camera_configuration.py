import uuid
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from api.models import Camera
from api.routers.cameras import _commit_camera, auto_configure_camera, auto_configure_existing_camera
from api.schemas import CameraAutoConfigure
from api.services.camera_discovery import _build_candidates, detect_camera_connection, DetectedCameraConnection


class CameraConfigurationTests(TestCase):
    def setUp(self):
        self.workspace = uuid.uuid4()
        self.user = SimpleNamespace(id=uuid.uuid4())

    def payload(self, **kwargs):
        return CameraAutoConfigure(workspace_id=self.workspace, host="192.168.15.131:8080", **kwargs)

    def test_camera_name_is_separate_from_login_and_credentials_can_be_empty(self):
        payload = self.payload(name="  cozinha  ")
        self.assertEqual(payload.name, "cozinha")
        self.assertEqual(payload.username, "")
        self.assertEqual(payload.password, "")
        with self.assertRaises(ValidationError):
            self.payload(name="   ")

    def test_http_port_is_probed_first_without_inventing_credentials(self):
        with patch("api.services.camera_discovery._port_is_open", return_value=True), patch(
            "api.services.camera_discovery._ffprobe_has_video", return_value=True
        ) as probe:
            detected = detect_camera_connection("192.168.15.131:8080", "", "")
        self.assertEqual(detected.stream_url, "http://192.168.15.131:8080/video")
        probe.assert_called_once_with(detected.stream_url)

    def test_nonstandard_http_port_and_encoded_credentials_are_preserved(self):
        candidates = _build_candidates(urlsplit("http://camera.local:8090/video"), "user", "p@ss")
        self.assertEqual(candidates[0], "http://user:p%40ss@camera.local:8090/video")
        self.assertTrue(any(url.startswith("http://user:p%40ss@camera.local:8090/") for url in candidates))

    def test_partial_credentials_are_rejected_before_network_probe(self):
        with patch("api.services.camera_discovery._port_is_open") as probe:
            with self.assertRaises(ValueError):
                detect_camera_connection("camera.local:8080", "user", "")
        probe.assert_not_called()

    def test_auto_configuration_uses_the_requested_camera_name(self):
        db = MagicMock()
        with patch("api.routers.cameras.require_workspace_membership", return_value=SimpleNamespace(role="owner")), patch(
            "api.routers.cameras._detect_connection", return_value=DetectedCameraConnection("https", "http-auto", "http://192.168.15.131:8080/video")
        ):
            camera = auto_configure_camera(self.payload(name="cozinha"), db, self.user)
        self.assertEqual(camera.name, "cozinha")
        self.assertEqual(camera.metadata_json["location"], "cozinha")
        self.assertEqual(camera.metadata_json["username"], "")
        db.commit.assert_called_once()

    def test_reconfiguring_without_name_keeps_the_existing_name(self):
        camera = Camera(id=uuid.uuid4(), workspace_id=self.workspace, name="cozinha", metadata_json={"location": "cozinha"})
        db = MagicMock()
        db.get.return_value = camera
        with patch("api.routers.cameras.require_workspace_membership", return_value=SimpleNamespace(role="owner")), patch(
            "api.routers.cameras._detect_connection", return_value=DetectedCameraConnection("https", "http-auto", "http://192.168.15.131:8080/video")
        ):
            auto_configure_existing_camera(camera.id, self.payload(), db, self.user)
        self.assertEqual(camera.name, "cozinha")
        self.assertEqual(camera.metadata_json["location"], "cozinha")

    def test_duplicate_name_returns_409_and_rolls_back(self):
        class DuplicateName(Exception):
            pgcode = "23505"
            diag = SimpleNamespace(constraint_name="cameras_workspace_id_name_key")
        db = MagicMock()
        db.commit.side_effect = IntegrityError("INSERT", {}, DuplicateName())
        with self.assertRaises(HTTPException) as error:
            _commit_camera(db, Camera())
        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("esse nome", error.exception.detail)
        db.rollback.assert_called_once()
        db.refresh.assert_not_called()

    def test_other_database_failures_are_not_misreported_as_duplicate_names(self):
        db = MagicMock()
        failure = IntegrityError("INSERT", {}, Exception("database failure"))
        db.commit.side_effect = failure
        with self.assertRaises(IntegrityError):
            _commit_camera(db, Camera())
        db.rollback.assert_called_once()
