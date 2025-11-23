"""
Pure Python SAME (Specific Area Message Encoding) Decoder

FSK demodulator for EAS messages with streaming support.
No external dependencies beyond NumPy/SciPy.
"""

import numpy as np
from scipy.io import wavfile
from scipy import signal as scipy_signal
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class PythonSAMEDecoder:
    """Pure Python SAME/EAS decoder with streaming support"""

    # SAME Protocol Constants
    MARK_FREQ = 2083.33      # Binary 1 (Hz)
    SPACE_FREQ = 1562.5      # Binary 0 (Hz)
    BAUD_RATE = 520.83       # Bits per second
    PREAMBLE_BYTE = 0xAB     # 10101011 binary
    PREAMBLE_COUNT = 16      # Number of preamble bytes

    def __init__(self, sample_rate: int = 22050):
        """
        Initialize SAME decoder

        Args:
            sample_rate: Audio sample rate in Hz (default 22050, multimon-ng standard)
        """
        self.sample_rate = sample_rate

        # Computed values
        self.samples_per_bit = sample_rate / self.BAUD_RATE  # ~42.3 samples/bit @ 22050Hz
        self.correlation_length = int(self.samples_per_bit)

        # Pre-compute correlation templates
        self.mark_i = None   # In-phase (cosine) for mark frequency
        self.mark_q = None   # Quadrature (sine) for mark frequency
        self.space_i = None  # In-phase (cosine) for space frequency
        self.space_q = None  # Quadrature (sine) for space frequency

        self._initialize_correlators()

        # Decoder state (for streaming)
        self.state = {}
        self.reset_state()

    def _initialize_correlators(self) -> None:
        """Pre-compute sine/cosine templates for FSK correlation detection"""
        # Generate time indices for one correlation window
        t = np.arange(self.correlation_length) / self.sample_rate

        # Mark frequency (2083.33 Hz) templates
        self.mark_i = np.cos(2 * np.pi * self.MARK_FREQ * t)
        self.mark_q = np.sin(2 * np.pi * self.MARK_FREQ * t)

        # Space frequency (1562.5 Hz) templates
        self.space_i = np.cos(2 * np.pi * self.SPACE_FREQ * t)
        self.space_q = np.sin(2 * np.pi * self.SPACE_FREQ * t)

    def reset_state(self) -> None:
        """Reset decoder state for new stream"""
        self.state = {
            'sync_locked': False,
            'bit_buffer': [],
            'byte_buffer': [],
            'current_byte': 0,
            'bit_count': 0,
            'messages': [],
            'integrator': 0,
            'in_message': False,
            'message_buffer': '',
        }

    def demodulate_fsk_with_decode(self, audio_samples: np.ndarray) -> List[int]:
        """
        Demodulate FSK audio and extract bytes directly.
        Closely follows multimon-ng's algorithm (demod_eas.c lines 278-401).

        Args:
            audio_samples: Float array of audio samples (-1.0 to 1.0)

        Returns:
            List of decoded bytes (0-255)
        """
        # Ensure audio is float
        if audio_samples.dtype != np.float32 and audio_samples.dtype != np.float64:
            audio_samples = audio_samples.astype(np.float64)

        num_samples = len(audio_samples)
        decoded_bytes = []

        # Constants (matching multimon-ng demod_eas.c)
        SUBSAMP = 2
        INTEGRATOR_MAX = 10
        DLL_GAIN_UNSYNC = 0.5
        DLL_GAIN_SYNC = 0.5
        DLL_MAX_INC = 8192

        # Phase accumulator and integrator (matching multimon-ng)
        # SPHASEINC = 0x10000 * BAUD * SUBSAMP / FREQ_SAMP
        phase_increment = int(0x10000 * self.BAUD_RATE * SUBSAMP / self.sample_rate)
        phase = 0
        integrator = 0

        # DCD shift register for tracking recent correlation results
        # Used to detect bit transitions for DLL
        dcd_shreg = 0

        # Shift register for assembled bits (LSB first)
        lasts = 0

        # State tracking
        sync_locked = False
        byte_counter = 0

        # Process with subsampling (every 2nd sample)
        i = 0
        while i < num_samples - self.correlation_length:
            window = audio_samples[i:i + self.correlation_length]

            # Correlate with mark frequency (I/Q)
            mark_i_corr = np.dot(window, self.mark_i)
            mark_q_corr = np.dot(window, self.mark_q)

            # Correlate with space frequency (I/Q)
            space_i_corr = np.dot(window, self.space_i)
            space_q_corr = np.dot(window, self.space_q)

            # Decision metric: f > 0 if mark, f < 0 if space
            f = (mark_i_corr**2 + mark_q_corr**2) - (space_i_corr**2 + space_q_corr**2)

            # Update DCD shift register
            # Keep last few correlation samples - when synchronized,
            # will have (nearly) single value per symbol
            dcd_shreg = (dcd_shreg << 1) & 0xFFFFFFFF
            if f > 0:
                dcd_shreg |= 1

            # Update integrator (acts as low-pass filter on bit decisions)
            if f > 0 and integrator < INTEGRATOR_MAX:
                integrator += 1
            elif f < 0 and integrator > -INTEGRATOR_MAX:
                integrator -= 1

            # DLL (Delay-Locked Loop) timing recovery
            # Check if transition occurred - want transitions near phase 0
            # XOR current bit with previous bit: if different, we have a transition
            dll_gain = DLL_GAIN_SYNC if sync_locked else DLL_GAIN_UNSYNC

            if (dcd_shreg ^ (dcd_shreg >> 1)) & 1:
                # Transition detected
                if phase < (0x8000 - (phase_increment // 8)):
                    # Before center; check for decrement
                    if phase > (phase_increment // 2):
                        adjustment = min(int(phase * dll_gain), DLL_MAX_INC)
                        phase -= adjustment
                else:
                    # After center; check for increment
                    if phase < (0x10000 - phase_increment // 2):
                        adjustment = min(int((0x10000 - phase) * dll_gain), DLL_MAX_INC)
                        phase += adjustment

            # Advance phase
            phase += phase_increment

            # Check if we've completed a bit period
            if phase >= 0x10000:
                phase = 1  # Reset to 1 (not 0) to match multimon-ng

                # Shift the bit register
                lasts >>= 1

                # Make bit decision based on integrator
                # If at least half of the values in integrator are 1, declare 1 received
                if integrator >= 0:
                    lasts |= 0x80

                # Check for sync pattern (0xAB preamble)
                # Do not resync when we're reading a message
                if lasts == self.PREAMBLE_BYTE and not sync_locked:
                    # Found sync - declare current offset as byte sync
                    sync_locked = True
                    byte_counter = 0
                    logger.debug(f"Sync found")

                # If synchronized, count bits and extract bytes
                elif sync_locked:
                    # Increment bit counter
                    byte_counter += 1

                    # Every 8 bits, we have a complete byte in lasts
                    if byte_counter == 8:
                        # Skip remaining preamble bytes (0xAB)
                        if lasts == self.PREAMBLE_BYTE:
                            byte_counter = 0
                            continue

                        # Check if character is valid SAME character
                        if self._is_valid_same_char(lasts):
                            decoded_bytes.append(lasts)
                            logger.debug(f"Decoded byte: 0x{lasts:02X} '{chr(lasts) if 32 <= lasts <= 126 else '?'}'")
                        else:
                            # Character not valid, lost sync
                            logger.debug(f"Invalid character 0x{lasts:02X}, lost sync")
                            sync_locked = False

                        byte_counter = 0

                        # Stop if we've decoded enough bytes
                        if len(decoded_bytes) > 300:
                            break

            # Advance by SUBSAMP samples
            i += SUBSAMP

        logger.info(f"Decoded {len(decoded_bytes)} bytes")
        return decoded_bytes

    def _is_valid_same_char(self, byte_val: int) -> bool:
        """
        Check if byte is a valid SAME protocol character.
        Based on multimon-ng's eas_allowed() function.

        Valid characters:
        - ASCII 32-126 (printable characters)
        - CR (13) and LF (10)
        - Rejects high-byte ASCII (0x80 and above)

        Args:
            byte_val: Byte value (0-255)

        Returns:
            True if valid SAME character
        """
        # High-byte ASCII characters are forbidden
        if byte_val & 0x80:
            return False

        # LF and CR are allowed
        if byte_val == 13 or byte_val == 10:
            return True

        # Printable ASCII characters are allowed
        if byte_val >= 32 and byte_val <= 126:
            return True

        return False

    def synchronize_bits(self, raw_bits: np.ndarray) -> Tuple[int, bool]:
        """
        Find preamble pattern by looking for 0xAB byte in shift register.
        Matches multimon-ng's approach.

        Args:
            raw_bits: Array of demodulated bits

        Returns:
            (bit_offset, found) where:
                bit_offset: Starting position of synchronized data (after preamble)
                found: Whether sync pattern was found
        """
        # Preamble is 0xAB byte repeated 16 times
        # Build shift register and look for 0xAB

        if len(raw_bits) < 8:
            return 0, False

        shift_reg = 0

        # Fill initial shift register with first 8 bits (LSB first)
        for i in range(8):
            shift_reg = (shift_reg >> 1) | ((raw_bits[i] & 1) << 7)

        # Scan through bits looking for 0xAB
        preamble_count = 0
        sync_position = -1

        for i in range(8, len(raw_bits)):
            # Check if current byte is 0xAB
            if shift_reg == 0xAB:
                if preamble_count == 0:
                    sync_position = i - 8  # Mark where preamble started
                preamble_count += 1

                # If we've seen enough preamble bytes, declare sync
                if preamble_count >= 4:  # At least 4 consecutive 0xAB bytes
                    # Skip past remaining preamble
                    data_start = sync_position + (self.PREAMBLE_COUNT * 8)
                    logger.info(f"Sync found at bit {sync_position}, data starts at {data_start}")
                    return data_start, True
            else:
                # Reset if we lose the pattern
                if preamble_count > 0:
                    preamble_count = 0
                    sync_position = -1

            # Shift in next bit (LSB first)
            shift_reg = (shift_reg >> 1) | ((raw_bits[i] & 1) << 7)

        logger.warning("No sync pattern found")
        return 0, False

    def assemble_bytes(self, bits: np.ndarray, start_offset: int) -> List[int]:
        """
        Convert bit stream to bytes (LSB first as per SAME spec).

        Args:
            bits: Synchronized bit array
            start_offset: Where to start reading

        Returns:
            List of byte values (0-255)
        """
        bytes_out = []
        pos = start_offset

        while pos + 8 <= len(bits):
            # Read 8 bits, LSB first
            byte_val = 0
            for bit_idx in range(8):
                if bits[pos + bit_idx]:
                    byte_val |= (1 << bit_idx)

            bytes_out.append(byte_val)
            pos += 8

            # Stop if we've read enough for a typical message (~268 chars max)
            if len(bytes_out) > 300:
                break

        return bytes_out

    def extract_messages(self, byte_stream: List[int]) -> List[Dict]:
        """
        Find SAME messages in byte stream.

        Args:
            byte_stream: List of decoded bytes

        Returns:
            List of message dictionaries matching decoder.py format
        """
        messages = []

        # Convert bytes to ASCII string, replace invalid chars
        try:
            text = ''.join(chr(b) if 32 <= b <= 126 else '?' for b in byte_stream)
        except Exception as e:
            logger.error(f"Failed to convert bytes to text: {e}")
            return messages

        # Look for ZCZC header
        zczc_pos = text.find('ZCZC')
        if zczc_pos == -1:
            logger.warning("No ZCZC header found in decoded text")
            return messages

        # Extract message after ZCZC until we hit invalid char or end marker
        message_start = zczc_pos + 4  # Skip "ZCZC"
        message_chars = []

        for i in range(message_start, len(text)):
            char = text[i]

            # Valid SAME characters: A-Z, 0-9, +, -
            if char == '-':
                message_chars.append(char)
                # Check if this is the ending dash
                if i + 1 < len(text) and text[i + 1] not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-':
                    break
            elif char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+':
                message_chars.append(char)
            else:
                # Invalid character, end of message
                break

        if message_chars:
            message_text = ''.join(message_chars)
            messages.append({
                'demod_name': 'EAS',
                'header_begin': 'ZCZC',
                'last_message': message_text
            })
            logger.info(f"Extracted message: {message_text}")

        # Check for EOM (NNNN)
        if 'NNNN' in text:
            logger.info("End of message (NNNN) detected")

        return messages

    def decode_stream(self, audio_samples: np.ndarray) -> List[Dict]:
        """
        Core streaming decoder - process audio chunk.

        Args:
            audio_samples: Audio data as float array

        Returns:
            List of message dictionaries
        """
        # Demodulate FSK and extract bytes directly
        byte_stream = self.demodulate_fsk_with_decode(audio_samples)

        # Extract messages from byte stream
        messages = self.extract_messages(byte_stream)

        return messages

    def decode_file(self, wav_path: str) -> Dict:
        """
        Decode SAME message from WAV file.

        Args:
            wav_path: Path to WAV file

        Returns:
            Dictionary matching current decoder.py format:
            {
                'success': bool,
                'messages': [...],
                'end_of_message': bool,
                'raw_output': str
            }
        """
        # Reset state for new file
        self.reset_state()

        try:
            # Read WAV file
            sample_rate, audio_data = wavfile.read(wav_path)

            # Convert to mono if stereo
            if len(audio_data.shape) > 1:
                audio_data = audio_data[:, 0]

            # Normalize to float -1.0 to 1.0
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float64) / 32768.0
            elif audio_data.dtype == np.int32:
                audio_data = audio_data.astype(np.float64) / 2147483648.0
            elif audio_data.dtype == np.uint8:
                audio_data = (audio_data.astype(np.float64) - 128) / 128.0

            # Resample if needed
            if sample_rate != self.sample_rate:
                logger.info(f"Resampling from {sample_rate} Hz to {self.sample_rate} Hz")
                # Use scipy's high-quality resampling
                num_samples = int(len(audio_data) * self.sample_rate / sample_rate)
                audio_data = scipy_signal.resample(audio_data, num_samples)

            # Decode
            messages = self.decode_stream(audio_data)

            # Format output to match decoder.py
            result = {
                'success': len(messages) > 0,
                'messages': messages,
                'end_of_message': False,  # Could detect NNNN if needed
                'raw_output': str(messages)
            }

            return result

        except Exception as e:
            logger.error(f"Decode failed: {e}", exc_info=True)
            return {
                'success': False,
                'messages': [],
                'end_of_message': False,
                'raw_output': f"Error: {str(e)}"
            }

    def decode_bytes(self, wav_data: bytes) -> Dict:
        """
        Decode WAV data from bytes.

        Args:
            wav_data: WAV file content as bytes

        Returns:
            Dictionary matching current decoder.py format
        """
        import tempfile
        import os

        # Write to temp file and decode
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(wav_data)
            temp_path = f.name

        try:
            return self.decode_file(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
