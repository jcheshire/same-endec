"""
SAME (Specific Area Message Encoding) Protocol Decoder

Wrapper for multimon-ng binary to decode EAS messages from WAV files.
"""

import subprocess
import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, List, Union


class SAMEDecoder:
    """Decoder for SAME protocol EAS messages using multimon-ng"""

    def __init__(self, multimon_binary_path: Optional[str] = None):
        """
        Initialize decoder with path to multimon-ng binary

        Args:
            multimon_binary_path: Path to multimon-ng binary. If None, searches in:
                - ../bin/multimon-ng
                - multimon-ng in PATH
        """
        if multimon_binary_path:
            self.binary_path = multimon_binary_path
        else:
            # Try to find binary in project bin directory
            project_bin = Path(__file__).parent.parent / "bin" / "multimon-ng"
            if project_bin.exists():
                self.binary_path = str(project_bin)
            else:
                # Fall back to PATH
                self.binary_path = "multimon-ng"

    def decode(self, wav_file_path: str, use_json: bool = True) -> Dict:
        """
        Decode a WAV file containing SAME encoded message

        Args:
            wav_file_path: Path to WAV file to decode
            use_json: If True, request JSON output from multimon-ng

        Returns:
            Dictionary containing decoded message information:
            {
                "success": bool,
                "messages": [
                    {
                        "header_begin": "ZCZC",
                        "last_message": "WXR-TOR-024031+0030-3171500-SCIENCE-",
                        "demod_name": "EAS"
                    }
                ],
                "end_of_message": bool,
                "raw_output": str
            }

        Raises:
            FileNotFoundError: If WAV file or binary not found
            RuntimeError: If decoding fails
            ValueError: If path validation fails
        """
        if not os.path.exists(wav_file_path):
            raise FileNotFoundError(f"WAV file not found: {wav_file_path}")

        # Security: Validate path to prevent command injection
        abs_path = os.path.abspath(wav_file_path)

        # Ensure file is actually a file (not a directory or special file)
        if not os.path.isfile(abs_path):
            raise ValueError("Path must be a regular file")

        # Validate WAV header magic bytes
        with open(abs_path, 'rb') as f:
            header = f.read(12)
            if len(header) < 12 or header[0:4] != b'RIFF' or header[8:12] != b'WAVE':
                raise ValueError("File is not a valid WAV file")

        # Build command - use only the absolute path (no user input in command)
        cmd = [self.binary_path, "-a", "EAS", "-t", "wav"]

        if use_json:
            cmd.append("--json")

        cmd.append(abs_path)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            return self._parse_output(result.stdout, use_json)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Decoding failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Decoding timed out after 30 seconds")
        except FileNotFoundError:
            raise FileNotFoundError(
                f"multimon-ng binary not found at: {self.binary_path}\n"
                "Make sure multimon-ng is compiled and placed in the bin/ directory"
            )

    def decode_bytes(self, wav_data: bytes, use_json: bool = True) -> Dict:
        """
        Decode WAV data from bytes (useful for API uploads)

        Args:
            wav_data: WAV file content as bytes
            use_json: If True, request JSON output from multimon-ng

        Returns:
            Dictionary containing decoded message (same format as decode())

        Raises:
            ValueError: If data is too large or invalid
        """
        # Security: Limit upload size to prevent DoS (10MB max)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        if len(wav_data) > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {len(wav_data)} bytes (max {MAX_FILE_SIZE})")

        # Security: Validate WAV header before writing to disk
        if len(wav_data) < 12 or wav_data[0:4] != b'RIFF' or wav_data[8:12] != b'WAVE':
            raise ValueError("Data is not a valid WAV file")

        # Create temporary file with secure permissions
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, mode='wb') as temp_file:
            temp_path = temp_file.name
            # Set restrictive permissions (owner read/write only)
            os.chmod(temp_path, 0o600)
            temp_file.write(wav_data)

        try:
            return self.decode(temp_path, use_json)
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass  # Best effort cleanup

    def _parse_output(self, output: str, is_json: bool) -> Dict:
        """
        Parse multimon-ng output into structured format

        Args:
            output: Raw output from multimon-ng
            is_json: Whether output is in JSON format

        Returns:
            Structured dictionary with decoded data
        """
        result = {
            "success": False,
            "messages": [],
            "end_of_message": False,
            "raw_output": output
        }

        if not output.strip():
            return result

        if is_json:
            # Parse JSON output (one JSON object per line)
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)

                    # Check for EOM
                    if "end_of_message" in data:
                        result["end_of_message"] = True

                    # Check for message
                    if "last_message" in data:
                        result["messages"].append(data)
                        result["success"] = True

                except json.JSONDecodeError:
                    continue
        else:
            # Parse text output
            # Format: "EAS: ZCZC-WXR-TOR-024031+0030-3171500-SCIENCE-"
            for line in output.strip().split('\n'):
                if "ZCZC" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        message_text = parts[1].strip()
                        # Remove "ZCZC-" prefix if present
                        if message_text.startswith("ZCZC"):
                            message_text = message_text[5:]  # Remove "ZCZC-"

                        result["messages"].append({
                            "demod_name": "EAS",
                            "header_begin": "ZCZC",
                            "last_message": message_text
                        })
                        result["success"] = True

                elif "NNNN" in line:
                    result["end_of_message"] = True

        return result

    def parse_same_message(self, message_string: str) -> Dict:
        """
        Parse a SAME message string into components

        Args:
            message_string: SAME string (e.g., "WXR-TOR-024031+0030-3171500-SCIENCE-")

        Returns:
            Dictionary with parsed components:
            {
                "org": "WXR",
                "event": "TOR",
                "locations": ["024031"],
                "duration": "+0030",
                "timestamp": "3171500",
                "originator": "SCIENCE"
            }
        """
        parts = message_string.strip().strip('-').split('-')

        result = {
            "org": None,
            "event": None,
            "locations": [],
            "duration": None,
            "timestamp": None,
            "originator": None
        }

        if len(parts) < 3:
            return result

        result["org"] = parts[0]
        result["event"] = parts[1]

        # Find duration (starts with +)
        duration_idx = None
        for i, part in enumerate(parts[2:], start=2):
            if part.startswith('+'):
                duration_idx = i
                break

        if duration_idx:
            # Everything between event and duration is location codes
            result["locations"] = parts[2:duration_idx]
            result["duration"] = parts[duration_idx]

            # Remaining parts are timestamp and originator
            if duration_idx + 1 < len(parts):
                result["timestamp"] = parts[duration_idx + 1]
            if duration_idx + 2 < len(parts):
                result["originator"] = parts[duration_idx + 2]

        return result


if __name__ == "__main__":
    # Example usage
    decoder = SAMEDecoder()

    # Test parsing
    test_message = "WXR-TOR-024031+0030-3171500-SCIENCE-"
    parsed = decoder.parse_same_message(test_message)
    print("Parsed message:", json.dumps(parsed, indent=2))
