import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from api.services.onesignal import send_push_to_subscription_ids


class OneSignalTests(unittest.TestCase):
    @patch("api.services.onesignal.urlopen")
    @patch("api.services.onesignal.get_settings")
    def test_event_metadata_is_sent_as_sdk_additional_data(self, settings, urlopen):
        settings.return_value = SimpleNamespace(onesignal_app_id="test-app", onesignal_api_key="test-key")
        data = {"notification_type": "armed_person_detected", "notification_id": "event-id"}
        send_push_to_subscription_ids(["subscription-id"], title="Pessoa armada", body="Camera Sala", data=data)
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["data"], data)
        self.assertNotIn("custom_data", payload)
        self.assertEqual(payload["include_subscription_ids"], ["subscription-id"])

    @patch("api.services.onesignal.urlopen", side_effect=TimeoutError("timeout"))
    @patch("api.services.onesignal.get_settings")
    def test_timeout_does_not_raise_after_notification_was_persisted(self, settings, urlopen):
        settings.return_value = SimpleNamespace(onesignal_app_id="test-app", onesignal_api_key="test-key")
        with self.assertLogs("api.services.onesignal", level="WARNING"):
            send_push_to_subscription_ids(["subscription-id"], title="Pessoa armada", body="Camera Sala")


if __name__ == "__main__":
    unittest.main()
