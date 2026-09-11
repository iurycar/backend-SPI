import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

from redis.exceptions import AuthenticationError, ConnectionError, TimeoutError

from extensions import verificar_conexao_redis


class RedisStartupTests(unittest.TestCase):
    def test_ping_uses_timeouts_and_closes_client(self):
        with patch('extensions.Redis.from_url') as factory:
            verificar_conexao_redis()
            factory.return_value.__enter__.return_value.ping.assert_called_once_with()
            factory.return_value.__exit__.assert_called_once()
            self.assertEqual(factory.call_args.kwargs['socket_connect_timeout'], 3)
            self.assertEqual(factory.call_args.kwargs['socket_timeout'], 3)

    def test_connection_failures_report_action_without_exposing_credentials(self):
        for error in (ConnectionError, TimeoutError, AuthenticationError, ValueError):
            with self.subTest(error=error), patch('extensions.Redis.from_url') as factory:
                factory.return_value.__enter__.return_value.ping.side_effect = error('secret-password')
                with self.assertRaises(RuntimeError) as raised:
                    verificar_conexao_redis()
                self.assertIn('REDIS_URL', str(raised.exception))
                self.assertNotIn('secret-password', str(raised.exception))
                factory.return_value.__exit__.assert_called_once()

    def test_dotenv_is_loaded_before_redis_url_is_read(self):
        configured_url = 'redis://redis-example:6380/2'
        def load_environment(*args):
            os.environ['REDIS_URL'] = configured_url

        source = Path(__file__).resolve().parents[1] / 'extensions.py'
        with patch.dict(os.environ), patch('dotenv.load_dotenv', side_effect=load_environment), patch('redis.Redis.from_url') as factory:
            namespace = runpy.run_path(str(source))
            self.assertEqual(namespace['REDIS_URL'], configured_url)
            factory.assert_called_once_with(configured_url, decode_responses=True)
