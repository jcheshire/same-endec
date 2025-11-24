"""
Test suite for SAME decoder

Tests both the current multimon-ng decoder and will be used to verify
the pure Python decoder implementation.

SPDX-License-Identifier: MIT
Copyright (c) 2025 Josh Cheshire
"""

import unittest
import os
import tempfile
import json
from pathlib import Path
from encoder import SAMEEncoder
from python_decoder import PythonSAMEDecoder as SAMEDecoder


class TestSAMEDecoder(unittest.TestCase):
    """Test cases for SAME decoder functionality"""

    @classmethod
    def setUpClass(cls):
        """Create test WAV files using the encoder"""
        # Create test directory in project to satisfy encoder security check
        cls.test_dir = os.path.join(os.getcwd(), 'test_wav_files')
        os.makedirs(cls.test_dir, exist_ok=True)
        cls.encoder = SAMEEncoder()
        cls.decoder = SAMEDecoder()

        # Test cases: (filename, SAME message, description)
        cls.test_cases = [
            (
                "tornado_warning.wav",
                "ZCZC-WXR-TOR-024031+0030-3191423-PHILLYWX-",
                "Tornado Warning for Montgomery County, MD"
            ),
            (
                "severe_thunderstorm.wav",
                "ZCZC-WXR-SVR-024031-024033+0100-3191500-PHILLYWX-",
                "Severe Thunderstorm Warning for multiple counties"
            ),
            (
                "flash_flood.wav",
                "ZCZC-WXR-FFW-024031+0045-3191600-PHILLYWX-",
                "Flash Flood Warning"
            ),
            (
                "test_weekly.wav",
                "ZCZC-WXR-RWT-024031+0015-3191700-PHILLYWX-",
                "Required Weekly Test"
            ),
            (
                "multiple_locations.wav",
                "ZCZC-WXR-TOR-024031-024033-024017-051013-051059+0030-3191800-PHILLYWX-",
                "Tornado Warning for 5 counties"
            ),
            (
                "subdivision_northwest.wav",
                "ZCZC-WXR-TOR-124031+0030-3191900-PHILLYWX-",
                "Tornado Warning for Northwest Montgomery County"
            ),
            (
                "long_duration.wav",
                "ZCZC-WXR-EVI-024031+0800-3192000-PHILLYWX-",
                "Evacuation Immediate - 8 hour duration"
            ),
        ]

        # Generate test WAV files
        cls.test_files = {}
        for filename, message, description in cls.test_cases:
            filepath = os.path.join(cls.test_dir, filename)
            cls.encoder.encode(message, output_path=filepath, include_eom=False)
            cls.test_files[filename] = {
                'path': filepath,
                'message': message,
                'description': description
            }
            print(f"Generated test file: {filename} - {description}")

    @classmethod
    def tearDownClass(cls):
        """Clean up test files"""
        import shutil
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def test_decode_tornado_warning(self):
        """Test decoding a basic tornado warning"""
        test_file = self.test_files['tornado_warning.wav']
        result = self.decoder.decode(test_file['path'], use_json=True)

        self.assertTrue(result['success'], "Decoding should succeed")
        self.assertGreater(len(result['messages']), 0, "Should have at least one message")

        # Check message content
        message = result['messages'][0]['last_message']
        self.assertIn('WXR', message, "Should contain originator code")
        self.assertIn('TOR', message, "Should contain event code")
        self.assertIn('024031', message, "Should contain FIPS code")

    def test_decode_multiple_locations(self):
        """Test decoding message with multiple location codes"""
        test_file = self.test_files['multiple_locations.wav']
        result = self.decoder.decode(test_file['path'], use_json=True)

        self.assertTrue(result['success'], "Decoding should succeed")
        message = result['messages'][0]['last_message']

        # Parse and verify locations
        parsed = self.decoder.parse_same_message(message)
        self.assertEqual(len(parsed['locations']), 5, "Should have 5 location codes")
        self.assertIn('024031', parsed['locations'])
        self.assertIn('051059', parsed['locations'])

    def test_decode_subdivision(self):
        """Test decoding message with county subdivision"""
        test_file = self.test_files['subdivision_northwest.wav']
        result = self.decoder.decode(test_file['path'], use_json=True)

        self.assertTrue(result['success'], "Decoding should succeed")
        message = result['messages'][0]['last_message']

        # Verify subdivision code (leading '1' indicates subdivision)
        self.assertIn('124031', message, "Should contain subdivision FIPS code")

    def test_parse_same_message_basic(self):
        """Test parsing a basic SAME message string"""
        message = "WXR-TOR-024031+0030-3191423-PHILLYWX-"
        parsed = self.decoder.parse_same_message(message)

        self.assertEqual(parsed['org'], 'WXR')
        self.assertEqual(parsed['event'], 'TOR')
        self.assertEqual(parsed['locations'], ['024031'])
        self.assertEqual(parsed['duration'], '+0030')
        self.assertEqual(parsed['timestamp'], '3191423')
        self.assertEqual(parsed['originator'], 'PHILLYWX')
        self.assertFalse(parsed['partial'])

    def test_parse_same_message_multiple_locations(self):
        """Test parsing SAME message with multiple locations"""
        message = "WXR-TOR-024031-024033-024017+0030-3191423-PHILLYWX-"
        parsed = self.decoder.parse_same_message(message)

        self.assertEqual(len(parsed['locations']), 3)
        self.assertIn('024031', parsed['locations'])
        self.assertIn('024033', parsed['locations'])
        self.assertIn('024017', parsed['locations'])

    def test_parse_same_message_concatenated_location_duration(self):
        """Test parsing when location and duration are concatenated"""
        # Some decoders might output "039039+0030" instead of "039039-+0030"
        message = "WXR-TOR-024031+0030-3191423-PHILLYWX-"
        parsed = self.decoder.parse_same_message(message)

        self.assertEqual(parsed['locations'], ['024031'])
        self.assertEqual(parsed['duration'], '+0030')

    def test_clean_same_message(self):
        """Test message cleaning removes noise"""
        noisy_message = "WXR-TOR-024031+0030-3191423-PHILLYWX-\x00\x01"
        cleaned = self.decoder.clean_same_message(noisy_message)

        self.assertNotIn('\x00', cleaned)
        self.assertNotIn('\x01', cleaned)
        self.assertIn('WXR', cleaned)
        self.assertIn('TOR', cleaned)

    def test_decode_bytes(self):
        """Test decoding from bytes instead of file path"""
        test_file = self.test_files['tornado_warning.wav']

        # Read file as bytes
        with open(test_file['path'], 'rb') as f:
            wav_data = f.read()

        # Decode from bytes
        result = self.decoder.decode_bytes(wav_data, use_json=True)

        self.assertTrue(result['success'], "Decoding from bytes should succeed")
        self.assertGreater(len(result['messages']), 0, "Should have at least one message")

    def test_invalid_wav_file(self):
        """Test that invalid WAV files are rejected"""
        # Create a fake WAV file
        fake_wav = os.path.join(self.test_dir, "fake.wav")
        with open(fake_wav, 'w') as f:
            f.write("This is not a WAV file")

        with self.assertRaises(ValueError):
            self.decoder.decode(fake_wav)

    def test_missing_file(self):
        """Test that missing files raise appropriate error"""
        with self.assertRaises(FileNotFoundError):
            self.decoder.decode("/nonexistent/file.wav")

    def test_file_too_large(self):
        """Test that oversized files are rejected"""
        # Create fake data larger than 10MB
        large_data = b'RIFF' + b'\x00' * 100 + b'WAVE' + b'\x00' * (11 * 1024 * 1024)

        with self.assertRaises(ValueError) as context:
            self.decoder.decode_bytes(large_data)

        self.assertIn("too large", str(context.exception))

    def test_duration_formats(self):
        """Test various duration formats"""
        test_cases = [
            ("+0015", "15 minutes"),
            ("+0030", "30 minutes"),
            ("+0100", "1 hour"),
            ("+0800", "8 hours"),
        ]

        for duration, description in test_cases:
            message = f"WXR-TOR-024031{duration}-3191423-PHILLYWX-"
            parsed = self.decoder.parse_same_message(message)
            self.assertEqual(parsed['duration'], duration,
                           f"Should parse {description} duration")

    def test_all_test_files_decode(self):
        """Verify all generated test files can be decoded"""
        for filename, fileinfo in self.test_files.items():
            with self.subTest(filename=filename):
                result = self.decoder.decode(fileinfo['path'], use_json=True)
                self.assertTrue(result['success'],
                              f"{filename} should decode successfully")

                # Verify the decoded message matches what we encoded
                if result['messages']:
                    decoded_msg = result['messages'][0]['last_message']
                    original_msg = fileinfo['message'].replace('ZCZC-', '')

                    # Check key components are present
                    parsed_original = self.decoder.parse_same_message(original_msg)
                    parsed_decoded = self.decoder.parse_same_message(decoded_msg)

                    self.assertEqual(parsed_original['org'], parsed_decoded['org'],
                                   f"{filename}: Originator should match")
                    self.assertEqual(parsed_original['event'], parsed_decoded['event'],
                                   f"{filename}: Event code should match")


class TestSAMEProtocolCompliance(unittest.TestCase):
    """Test SAME protocol compliance and edge cases"""

    def setUp(self):
        self.decoder = SAMEDecoder()

    def test_valid_event_codes(self):
        """Test parsing various valid event codes"""
        valid_codes = ['TOR', 'SVR', 'FFW', 'EVI', 'RWT', 'RMT', 'NPT', 'EAN']

        for code in valid_codes:
            message = f"WXR-{code}-024031+0030-3191423-TEST-"
            parsed = self.decoder.parse_same_message(message)
            self.assertEqual(parsed['event'], code)

    def test_valid_originator_codes(self):
        """Test parsing various originator codes"""
        valid_orgs = ['WXR', 'PEP', 'CIV', 'EAS']

        for org in valid_orgs:
            message = f"{org}-TOR-024031+0030-3191423-TEST-"
            parsed = self.decoder.parse_same_message(message)
            self.assertEqual(parsed['org'], org)

    def test_timestamp_format(self):
        """Test timestamp parsing (Julian day + HHMM)"""
        # Format: JJJHHMM (Julian day 001-366, hour 00-23, minute 00-59)
        message = "WXR-TOR-024031+0030-3652359-TEST-"
        parsed = self.decoder.parse_same_message(message)

        self.assertEqual(parsed['timestamp'], '3652359')
        self.assertEqual(len(parsed['timestamp']), 7)

    def test_callsign_max_length(self):
        """Test that callsigns up to 8 characters are accepted"""
        message = "WXR-TOR-024031+0030-3191423-ABCDEFGH-"
        parsed = self.decoder.parse_same_message(message)

        self.assertEqual(parsed['originator'], 'ABCDEFGH')
        self.assertEqual(len(parsed['originator']), 8)


def run_tests():
    """Run all tests and display results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSAMEDecoder))
    suite.addTests(loader.loadTestsFromTestCase(TestSAMEProtocolCompliance))

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
