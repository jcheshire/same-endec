"""
SAME (Specific Area Message Encoding) Protocol Encoder

Generates EAS (Emergency Alert System) audio signals using FSK modulation.
Based on the SAME protocol specification.
"""

import numpy as np
from scipy.io import wavfile
import datetime
import io
import os
import re
from typing import Optional, Union


class SAMEEncoder:
    """Encoder for SAME protocol EAS messages"""

    # SAME Protocol Constants
    MARK_FREQUENCY = 2083 + (1/3)  # Hz - binary 1
    SPACE_FREQUENCY = 1562.5        # Hz - binary 0
    BAUD_RATE = 520 + (5/6)         # bits per second
    SAMPLE_RATE = 43750             # Hz

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.bit_duration = 1.0 / self.BAUD_RATE

    def _mark_bit(self) -> np.ndarray:
        """Generate a mark bit (binary 1) at 2083.33 Hz"""
        samples = np.arange(self.bit_duration * self.sample_rate) / self.sample_rate
        return np.sin(2 * np.pi * self.MARK_FREQUENCY * samples) * 0.8

    def _space_bit(self) -> np.ndarray:
        """Generate a space bit (binary 0) at 1562.5 Hz"""
        samples = np.arange(self.bit_duration * self.sample_rate) / self.sample_rate
        return np.sin(2 * np.pi * self.SPACE_FREQUENCY * samples)

    def _encode_byte(self, byte_char: str) -> np.ndarray:
        """Encode a single character as FSK audio (LSB first)"""
        byte_data = np.zeros(0)
        byte_value = ord(byte_char)

        for i in range(8):
            if byte_value >> i & 1:
                byte_data = np.append(byte_data, self._mark_bit())
            else:
                byte_data = np.append(byte_data, self._space_bit())

        return byte_data

    def _generate_preamble(self) -> np.ndarray:
        """Generate SAME preamble (16 bytes of 0xAB pattern)"""
        byte_data = np.zeros(0)

        # 0xAB = 10101011 in binary, transmitted LSB first
        # This creates the characteristic SAME attention tone
        for _ in range(16):
            byte_data = np.append(byte_data, self._mark_bit())
            byte_data = np.append(byte_data, self._mark_bit())
            byte_data = np.append(byte_data, self._space_bit())
            byte_data = np.append(byte_data, self._mark_bit())
            byte_data = np.append(byte_data, self._space_bit())
            byte_data = np.append(byte_data, self._mark_bit())
            byte_data = np.append(byte_data, self._space_bit())
            byte_data = np.append(byte_data, self._mark_bit())

        return byte_data

    def encode(self, same_message: str, output_path: Optional[str] = None) -> Union[bytes, str]:
        """
        Encode a SAME message into WAV audio

        Args:
            same_message: SAME format string (e.g., "ZCZC-WXR-TOR-024031+0030-1234567-SCIENCE-")
            output_path: Optional path to save WAV file. If None, returns bytes.

        Returns:
            If output_path is provided, returns the path. Otherwise returns WAV file as bytes.

        Raises:
            ValueError: If message is too long or output_path is invalid
        """
        # Security: Validate message length to prevent DoS
        if len(same_message) > 268:  # SAME spec max message length
            raise ValueError(f"Message too long: {len(same_message)} chars (max 268)")

        # Security: Validate output_path if provided
        if output_path:
            # Convert to absolute path and check for path traversal
            abs_path = os.path.abspath(output_path)
            # Ensure it's in a safe location (current directory or subdirectories only)
            if not abs_path.startswith(os.path.abspath(os.getcwd())):
                raise ValueError("Output path must be within current working directory")
            # Prevent writing to sensitive locations
            if abs_path.startswith('/etc') or abs_path.startswith('/sys') or abs_path.startswith('/proc'):
                raise ValueError("Cannot write to system directories")

        signal = np.zeros(20000)

        # Transmit message header 3 times (SAME protocol requirement)
        for _ in range(3):
            signal = np.append(signal, self._generate_preamble())

            # Encode each character
            for char in same_message:
                signal = np.append(signal, self._encode_byte(char))

            # One second silence between transmissions
            signal = np.append(signal, np.zeros(self.sample_rate))

        # Transmit End-Of-Message (NNNN) 3 times
        for _ in range(3):
            signal = np.append(signal, self._generate_preamble())

            for char in "NNNN":
                signal = np.append(signal, self._encode_byte(char))

            signal = np.append(signal, np.zeros(self.sample_rate))

        # Convert to 16-bit PCM
        signal *= 32767
        signal = np.int16(signal)

        if output_path:
            wavfile.write(output_path, self.sample_rate, signal)
            return output_path
        else:
            # Return as bytes
            buffer = io.BytesIO()
            wavfile.write(buffer, self.sample_rate, signal)
            buffer.seek(0)
            return buffer.read()


def build_same_message(
    event_code: str,
    location_codes: list,
    duration: str,
    timestamp: Optional[str] = None,
    originator: str = "SCIENCE"
) -> str:
    """
    Build a properly formatted SAME message string

    Args:
        event_code: 3-letter event code (e.g., "TOR", "SVR", "RWT")
        location_codes: List of 6-digit FIPS location codes
        duration: Duration in +HHMM format (e.g., "+0030" for 30 minutes)
        timestamp: Optional JJJHHMM timestamp. If None, uses current time.
        originator: Originator code (default "SCIENCE")

    Returns:
        Formatted SAME message string

    Raises:
        ValueError: If input validation fails

    Example:
        >>> build_same_message("TOR", ["024031"], "+0030", originator="NWS/KMMS")
        "ZCZC-WXR-TOR-024031+0030-3171500-NWS/KMMS-"
    """
    # Security: Validate all inputs
    if not re.match(r'^[A-Z]{3}$', event_code):
        raise ValueError("event_code must be exactly 3 uppercase letters")

    if not location_codes or len(location_codes) > 31:
        raise ValueError("location_codes must contain 1-31 location codes")

    for code in location_codes:
        if not re.match(r'^\d{6}$', code):
            raise ValueError(f"Invalid location code: {code}. Must be 6 digits")

    if not re.match(r'^\+\d{4}$', duration):
        raise ValueError("duration must be in +HHMM format (e.g., +0030)")

    if timestamp is None:
        timestamp = datetime.datetime.now().strftime("%j%H%M")
    elif not re.match(r'^\d{7}$', timestamp):
        raise ValueError("timestamp must be 7 digits (JJJHHMM format)")

    # Validate originator (8 chars max, alphanumeric and / - allowed)
    if not re.match(r'^[A-Z0-9/\- ]{1,8}$', originator):
        raise ValueError("originator must be 1-8 characters (letters, numbers, /, -, space)")

    # Determine ORG code based on event
    if event_code in ["EAN", "EAT", "NIC", "NPT", "RMT", "RWT"]:
        org = "PEP"
    elif event_code in ["TOR", "SVR", "FFW", "EVI"]:
        org = "WXR"
    else:
        org = "CIV"

    # Build location string
    locations = "-".join(location_codes)

    return f"ZCZC-{org}-{event_code}-{locations}{duration}-{timestamp}-{originator}-"


if __name__ == "__main__":
    # Example usage
    encoder = SAMEEncoder()

    # Build a test message
    message = build_same_message(
        event_code="TOR",
        location_codes=["024031"],
        duration="+0030",
        originator="SCIENCE"
    )

    print(f"Encoding message: {message}")
    encoder.encode(message, "test_output.wav")
    print("Saved to test_output.wav")
