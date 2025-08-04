"""Tests for the CSV Writer module"""

import asyncio
import unittest
from unittest.mock import patch, mock_open
from vvm_to_signalk.csv_writer import CsvWriter, CsvWriterConfig
from vvm_to_signalk.config_decoder import EngineParameter, EngineParameterType

class TestCsvWriterConfig(unittest.TestCase):
    """Test the CsvWriterConfig class"""

    def test_default_config(self):
        config = CsvWriterConfig()
        self.assertFalse(config.enabled)
        self.assertEqual(config.filename, "./logs/data.csv")
        self.assertEqual(config.flush_interval, 1.0)

    def test_read_dict(self):
        data = {
            "enabled": True,
            "filename": "/tmp/test_csv.csv",
            "interval": 5.0
        }
        config = CsvWriterConfig(data)
        self.assertTrue(config.enabled)
        self.assertEqual(config.filename, "/tmp/test_csv.csv")
        self.assertEqual(config.flush_interval, 5.0)

    def test_valid_property(self):
        config = CsvWriterConfig()
        self.assertTrue(config.valid)
        config.enabled = True
        config.filename = None
        self.assertFalse(config.valid)
        config.filename = "test.csv"
        self.assertTrue(config.valid)
        config.flush_interval = 0
        self.assertFalse(config.valid)

class TestCsvWriter(unittest.TestCase):
    """Test the CsvWriter class"""

    def setUp(self):
        self.config = CsvWriterConfig()
        self.config.enabled = True
        self.config.filename = "/tmp/test.csv"
        self.config.flush_interval = 0.1
        self.csv_writer = CsvWriter(self.config)

    def test_update_parameters(self):
        params = [
            EngineParameter(EngineParameterType.ENGINE_RPM.value, 0),
            EngineParameter(257, 1)
        ]
        self.assertTrue(self.csv_writer.update_engine_parameters(params))
        expected_fieldnames = ["timestamp", "0_ENGINE_RPM", "1_COOLANT_TEMPERATURE"]
        self.assertEqual(self.csv_writer._CsvWriter__fieldnames, expected_fieldnames)
        self.assertTrue(self.csv_writer._CsvWriter__wrote_fieldnames)

        # Test that parameters are not updated after writing fieldnames
        self.assertFalse(self.csv_writer.update_engine_parameters([EngineParameter(2, EngineParameterType.BATTERY_VOLTAGE.value)]))
        self.assertEqual(self.csv_writer._CsvWriter__fieldnames, expected_fieldnames)

    @patch('builtins.open', new_callable=mock_open)
    @patch('csv.DictWriter')
    def test_open_output_file(self, mock_dict_writer, mock_open_file):
        self.csv_writer.update_engine_parameters([EngineParameter(0, EngineParameterType.ENGINE_RPM.value)])
        mock_open_file.assert_called_once_with(self.config.filename, 'a', newline='', encoding="utf-8")
        mock_dict_writer.assert_called_once_with(mock_open_file(), fieldnames=self.csv_writer._CsvWriter__fieldnames)
        mock_dict_writer().writeheader.assert_called_once()
        self.assertTrue(self.csv_writer._CsvWriter__wrote_fieldnames)

        # Test with disabled config
        self.config.enabled = False
        mock_open_file.reset_mock()
        self.assertFalse(self.csv_writer.open_output_file())
        mock_open_file.assert_not_called()

        # Test with no fieldnames
        self.config.enabled = True
        self.csv_writer._CsvWriter__fieldnames = None
        mock_open_file.reset_mock()
        self.assertFalse(self.csv_writer.open_output_file())
        mock_open_file.assert_not_called()
        self.assertFalse(self.config.enabled) # Should disable config if no fieldnames

    async def test_accept_engine_data(self):
        self.csv_writer.update_engine_parameters([EngineParameter(0, EngineParameterType.ENGINE_RPM.value)])
        self.csv_writer.open_output_file()
        param = EngineParameter(0, EngineParameterType.ENGINE_RPM.value)
        value = 1500
        await self.csv_writer.accept_engine_data(param, value)
        self.assertEqual(self.csv_writer._CsvWriter__data["0_ENGINE_RPM"], value)
        self.assertIsNotNone(self.csv_writer._CsvWriter__data["timestamp"])
        self.assertIsNotNone(self.csv_writer._CsvWriter__timer)
        # Store the timer task locally for explicit cleanup
        timer_task = self.csv_writer._CsvWriter__timer
        # Explicitly await the timer task to ensure it completes
        await timer_task
        self.assertIsNone(self.csv_writer._CsvWriter__timer)

        # Test with disabled config
        self.config.enabled = False
        await self.csv_writer.accept_engine_data(param, value)
        # No timer should be created if disabled
        self.assertIsNone(self.csv_writer._CsvWriter__timer)

        # Ensure the timer task is cancelled if it was created (for the disabled case)
        if timer_task and not timer_task.done():
            timer_task.cancel()
            try:
                await timer_task
            except asyncio.CancelledError:
                pass

        # Ensure the timer task is cancelled if it was created
        if self.csv_writer._CsvWriter__timer:
            self.csv_writer._CsvWriter__timer.cancel()
            try:
                await self.csv_writer._CsvWriter__timer
            except asyncio.CancelledError:
                pass