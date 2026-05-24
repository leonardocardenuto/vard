from __future__ import annotations

import unittest

from fall_detection.stream_url import normalize_stream_url


class NormalizeStreamUrlTests(unittest.TestCase):
    def test_encodes_special_characters_in_credentials(self):
        source = "rtsp://vard-zero:wAOWOa8IfdydJP9s3^%w@192.168.0.91:554/stream1"

        normalized = normalize_stream_url(source)

        self.assertEqual(
            normalized,
            "rtsp://vard-zero:wAOWOa8IfdydJP9s3%5E%25w@192.168.0.91:554/stream1",
        )

    def test_does_not_double_encode_credentials(self):
        source = "rtsp://user:already%25encoded@192.168.0.91:554/stream1"

        normalized = normalize_stream_url(source)

        self.assertEqual(
            normalized,
            "rtsp://user:already%25encoded@192.168.0.91:554/stream1",
        )


if __name__ == "__main__":
    unittest.main()
