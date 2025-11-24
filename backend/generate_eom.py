#!/usr/bin/env python3
"""
Generate static End-Of-Message (EOM) WAV file
This only needs to be run once - EOM is always "NNNN"

SPDX-License-Identifier: MIT
Copyright (c) 2025 Josh Cheshire
"""

from encoder import SAMEEncoder

def main():
    encoder = SAMEEncoder()

    # Encode just "NNNN" as a complete message
    # The encoder will add the preamble and repeat 3 times
    eom_wav = encoder.encode("NNNN", include_eom=False)

    # Actually, we need to manually generate just the EOM part
    # Let me create a simpler version that just encodes NNNN 3 times
    import numpy as np
    from scipy.io import wavfile

    signal = np.zeros(20000)

    # Transmit End-Of-Message (NNNN) 3 times
    for _ in range(3):
        signal = np.append(signal, encoder._generate_preamble())

        for char in "NNNN":
            signal = np.append(signal, encoder._encode_byte(char))

        # One second silence between transmissions
        signal = np.append(signal, np.zeros(encoder.sample_rate))

    # Convert to 16-bit PCM
    signal *= 32767
    signal = np.int16(signal)

    # Save to frontend directory so it's served as a static file
    output_path = "../frontend/eom.wav"
    wavfile.write(output_path, encoder.sample_rate, signal)

    print(f"Generated EOM WAV file: {output_path}")
    print(f"File size: {len(signal) * 2} bytes")
    print(f"Duration: {len(signal) / encoder.sample_rate:.2f} seconds")

if __name__ == "__main__":
    main()
