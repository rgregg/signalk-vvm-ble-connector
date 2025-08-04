"""Tests for the FuturesQueue module"""

import unittest
import asyncio
from unittest.mock import MagicMock
from vvm_to_signalk.futures_queue import FuturesQueue

class TestFuturesQueue(unittest.IsolatedAsyncioTestCase):
    """Test the FuturesQueue class"""

    def setUp(self):
        self.queue = FuturesQueue()

    async def test_register_and_trigger(self):
        key = "test_key"
        value = "test_value"

        future = self.queue.register(key)
        self.assertFalse(future.done())

        self.queue.trigger(key, value)
        self.assertTrue(future.done())
        self.assertEqual(await future, value)

        # Test that registering the same key after it's been triggered creates a new future
        new_future = self.queue.register(key)
        self.assertNotEqual(future, new_future)
        self.assertFalse(new_future.done())

    async def test_register_callback(self):
        key = "callback_key"
        value = "callback_value"
        mock_callback = MagicMock()

        future = self.queue.register(key)
        self.queue.register_callback(key, mock_callback)
        self.queue.trigger(key, value)

        # Give a moment for the callback to execute
        await asyncio.sleep(0.01)
        mock_callback.assert_called_once_with(future)

    async def test_trigger_no_listener(self):
        key = "no_listener_key"
        value = "some_value"

        # Triggering a key with no registered listener should not raise an error
        self.queue.trigger(key, value)

    async def test_wait_for_data(self):
        key = "wait_key"
        value = "wait_value"

        async def trigger_after_delay():
            await asyncio.sleep(0.05)
            self.queue.trigger(key, value)

        future = self.queue.register(key)
        asyncio.get_running_loop().create_task(trigger_after_delay())
        result = await self.queue.wait_for_data(key, timeout=0.1, default_value=None)
        self.assertEqual(result, value)

    async def test_wait_for_data_timeout(self):
        key = "timeout_key"
        default = "default_value"

        result = await self.queue.wait_for_data(key, timeout=0.01, default_value=default)
        self.assertEqual(result, default)

    async def test_wait_for_data_existing_future(self):
        key = "existing_future_key"
        value = "existing_future_value"

        # Register and trigger the future first
        future = self.queue.register(key)
        self.queue.trigger(key, value)

        # Now call wait_for_data. It should return the default value as the future is already done and removed.
        result = await self.queue.wait_for_data(key, timeout=0.1, default_value=None)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()