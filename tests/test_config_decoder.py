"""Test the decoding of data from BLE signal"""
import logging
import unittest
from vvm_to_signalk.config_decoder import ConfigDecoder

logger = logging.getLogger(__name__)

class Test_ConfigDecoderTests(unittest.IsolatedAsyncioTestCase):
    """Test decoder implementation"""
    
    def test_simple(self):
        """Configure a decoder with a sample payload"""

        decoder = ConfigDecoder()
        decoder.add(bytes.fromhex("0028b6000100000001000001d2000002e8000003"))
        decoder.add(bytes.fromhex("0170170004960000050a000006401f0007102700"))
        decoder.add(bytes.fromhex("0208b5000009d400000ab600000bfb00000c0000"))
        decoder.add(bytes.fromhex("03000d0000000e00000100000001010000010200"))
        decoder.add(bytes.fromhex("0400010300000104000001050000010600000107"))
        decoder.add(bytes.fromhex("0500000108000001090000010a0000010b000001"))
        decoder.add(bytes.fromhex("060c0000010d0000010e00000200000002010000"))
        decoder.add(bytes.fromhex("0702020000020300000204000002050000020600"))
        decoder.add(bytes.fromhex("0800020700000208000002090000020a0000020b"))
        decoder.add(bytes.fromhex("090000020c0000020d0000020e0000"))

        decoder.combine_and_parse_data()
        assert decoder.has_all_data

    def test_incomplete_data(self):
        """Test that the decoder correctly handles incomplete data."""
        decoder = ConfigDecoder()
        decoder.add(bytes.fromhex("0028b6000100000001000001d2000002e8000003"))
        decoder.add(bytes.fromhex("0170170004960000050a000006401f0007102700"))
        with self.assertRaises(ValueError):
            decoder.combine_and_parse_data()
        self.assertFalse(decoder.has_all_data)

    def test_out_of_order_data(self):
        """Test that the decoder correctly handles data that arrives out of order."""
        decoder = ConfigDecoder()
        decoder.add(bytes.fromhex("090000020c0000020d0000020e0000"))
        decoder.add(bytes.fromhex("0028b6000100000001000001d2000002e8000003"))
        decoder.add(bytes.fromhex("0170170004960000050a000006401f0007102700"))
        decoder.add(bytes.fromhex("0208b5000009d400000ab600000bfb00000c0000"))
        decoder.add(bytes.fromhex("03000d0000000e00000100000001010000010200"))
        decoder.add(bytes.fromhex("0400010300000104000001050000010600000107"))
        decoder.add(bytes.fromhex("0500000108000001090000010a0000010b000001"))
        decoder.add(bytes.fromhex("060c0000010d0000010e00000200000002010000"))
        decoder.add(bytes.fromhex("0702020000020300000204000002050000020600"))
        decoder.add(bytes.fromhex("0800020700000208000002090000020a0000020b"))
        
        decoder.combine_and_parse_data()
        self.assertTrue(decoder.has_all_data)

    def test_invalid_data(self):
        """Test that the decoder correctly handles invalid data."""
        decoder = ConfigDecoder()
        decoder.add(bytes.fromhex("0028b6000100000001000001d2000002e8000003"))
        decoder.add(bytes.fromhex("0170170004960000050a000006401f0007102700"))
        decoder.add(bytes.fromhex("0208b5000009d400000ab600000bfb00000c0000"))
        decoder.add(bytes.fromhex("03000d0000000e00000100000001010000010200"))
        decoder.add(bytes.fromhex("0400010300000104000001050000010600000107"))
        decoder.add(bytes.fromhex("0500000108000001090000010a0000010b000001"))
        decoder.add(bytes.fromhex("060c0000010d0000010e00000200000002010000"))
        decoder.add(bytes.fromhex("0702020000020300000204000002050000020600"))
        decoder.add(bytes.fromhex("0800020700000208000002090000020a0000020b"))
        # This chunk is intentionally missing to cause a length error
        # decoder.add(bytes.fromhex("090000020c0000020d0000020e0000"))
        
        with self.assertRaises(ValueError):
            decoder.combine_and_parse_data()

    def test_empty_data(self):
        """Test that the decoder correctly handles empty data."""
        decoder = ConfigDecoder()
        with self.assertRaises(ValueError):
            decoder.combine_and_parse_data()
        self.assertIsNone(decoder.has_all_data)

if __name__ == "__main__":
    unittest.main()