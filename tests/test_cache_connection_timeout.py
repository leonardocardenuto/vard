from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from api.cache.response_cache import RedisError, get_response_cache


class OptionalCacheConnectionTests(TestCase):
    def tearDown(self):
        get_response_cache.cache_clear()

    def test_unreachable_cache_has_bounded_timeouts_and_falls_back(self):
        get_response_cache.cache_clear()
        with patch('api.cache.response_cache.get_settings', return_value=SimpleNamespace(redis_url='redis://unreachable:6379')), \
             patch('api.cache.response_cache.Redis') as redis:
            redis.from_url.return_value.ping.side_effect = RedisError('unavailable')
            cache = get_response_cache()
            self.assertIsNone(cache.client)
            options = redis.from_url.call_args.kwargs
            self.assertEqual(options['socket_connect_timeout'], 1.0)
            self.assertEqual(options['socket_timeout'], 1.0)
            self.assertFalse(options['retry_on_timeout'])
