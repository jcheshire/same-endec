# Python SAME Decoder - Debug Notes

## ✅ IMPLEMENTATION COMPLETE

The pure Python SAME decoder is now fully functional with streaming support!

### What's Working
- ✅ Test suite created (17 tests, **ALL PASS**)
- ✅ Encoder generates valid SAME WAV files
- ✅ FSK demodulation with I/Q correlation
- ✅ Resampling from encoder's 43750 Hz → 22050 Hz
- ✅ Phase accumulator for bit timing (matches multimon-ng)
- ✅ Integrator for noise-robust bit decisions
- ✅ **DLL (Delay-Locked Loop) timing recovery implemented**
- ✅ Preamble detection (0xAB sync pattern)
- ✅ Byte extraction directly during demodulation
- ✅ Message parsing and validation
- ✅ **Streaming support** - microphone, live radio, audio loopback
- ✅ **L2 state machine** - protocol-aware message assembly

### Key Implementation Details

**Layer 1 (Physical - FSK Demodulation):**
1. **DLL timing recovery** (lines 150-166) - adjusts phase when bit transitions occur to keep sampling centered
2. **Direct byte extraction** during FSK demodulation - no separate synchronization step needed
3. **Preamble skipping** - detects 0xAB for sync, then skips remaining preamble bytes
4. **State persistence** - all L1 state (phase, integrator, sync, etc.) preserved between chunks

**Layer 2 (Message Assembly):**
1. **SAME protocol parser** - understands message structure: `-ORG-EVT-LOC+DUR-TIME-CALL-`
2. **Continuous listening** - emits messages as headers complete, keeps listening indefinitely
3. **NNNN detection** - recognizes end-of-message marker without stopping decoder
4. **Audio buffering** - maintains correlation window across chunk boundaries

### Use Cases Supported
- 📁 **WAV file decoding** - `decode_file()` for batch processing
- 🎤 **Microphone input** - `process_audio_chunk()` for live monitoring
- 📻 **Internet radio streams** - continuous real-time decoding
- 🔊 **Software audio loopback** - monitor system audio

## The Problem

The encoder creates valid FSK audio that multimon-ng successfully decodes:
```bash
../bin/multimon-ng -a EAS -t wav --json test.wav
# Returns: {"demod_name":"EAS","header_begin":"ZCZC","last_message":"-WXR-TOR-024031+0030-3191423-PHILLYWX-"}
```

But our Python decoder demodulates ~3190 bits and never finds the 0xAB preamble byte.

## Technical Details

### Encoder Settings
- Sample rate: 43750 Hz
- Mark frequency: 2083.33 Hz (binary 1)
- Space frequency: 1562.5 Hz (binary 0)
- Baud rate: 520.83 bps
- Leading silence: 20,000 samples (~0.46 seconds)
- Preamble: 16 bytes of 0xAB

### Decoder Settings
- Target sample rate: 22050 Hz (matches multimon-ng)
- Correlation window: 42 samples (≈1 bit period)
- Subsampling: Every 2 samples (SUBSAMP=2)
- Phase increment: 0xC17 (3095) - wraps every ~21 correlation samples
- Integrator range: ±10

### Demodulation Output
- Total bits decoded: ~3190
- First ~240 bits: all 1s (expected - leading silence)
- Bits 240-280 show activity but no 0xAB pattern found
- Example bit sequence at 240: `00000110000001100000011000011100010011`
  - These would form bytes like 0x60, not 0xAB

## What We've Tried

1. **Simple correlation**: Sample once per bit period
   - Result: Multiple detections per bit, no clear pattern

2. **Phase accumulator + integrator** (current): Matches multimon-ng approach
   - Correlate every 2 samples
   - Accumulate phase
   - Use integrator to smooth bit decisions
   - Make decision when phase wraps
   - Result: Still no 0xAB pattern

## Likely Issues

1. **Timing recovery**: Even with phase accumulator, we might not be sampling at the right phase within each bit
2. **Correlation window alignment**: Window might not be centered on the bit
3. **Integrator initialization**: Might need different starting conditions
4. **Frequency accuracy**: Templates use exact 2083.33/1562.5 Hz, encoder might have slight differences

## Next Steps to Try

1. **Add DLL (Delay-Locked Loop)**: multimon-ng adjusts phase based on bit transitions
   - Lines 328-349 in demod_eas.c
   - Adjusts sampling point to center of bit period

2. **Debug correlation values**: Print actual correlation strengths to see if frequencies are detected

3. **Try different phase offsets**: Manually try different starting phases to find alignment

4. **Compare with working decoder**: Run multimon-ng with verbose output to see what it detects

5. **Check encoder output**: Verify encoder is actually generating proper FSK (use FFT analysis)

## Files

- `backend/python_decoder.py` - Pure Python decoder implementation
- `backend/decoder.py` - Original multimon-ng wrapper (working)
- `backend/encoder.py` - SAME encoder (working, creates valid output)
- `backend/test_decoder.py` - Test suite (17 tests)
- `bin/multimon-ng` - Compiled C decoder (working baseline)

## Test Command

```bash
cd backend

# Generate test file
./venv/bin/python -c "
from encoder import SAMEEncoder
encoder = SAMEEncoder()
encoder.encode('ZCZC-WXR-TOR-024031+0030-3191423-PHILLYWX-', 'test.wav', include_eom=False)
"

# Test with multimon-ng (works)
../bin/multimon-ng -a EAS -t wav --json test.wav

# Test with Python decoder (doesn't work yet)
./venv/bin/python -c "
from python_decoder import PythonSAMEDecoder
decoder = PythonSAMEDecoder()
result = decoder.decode_file('test.wav')
print(result)
"
```

## Key Multimon-ng Code References

- `multimon-ng/demod_eas.c` lines 278-401: Main demodulation loop
- Line 296-299: Correlation calculation (mark - space)
- Line 307-314: Integrator update
- Line 328-349: DLL timing adjustment (WE DON'T HAVE THIS YET)
- Line 351-362: Phase accumulator and bit decision
- Line 368-375: Sync detection (looks for 0xAB in shift register)

## Research Done

Looked at:
- [arXiv FSK paper](https://arxiv.org/html/2402.17777v1) - Too simplistic for our needs
- [alltheFSKs library](https://github.com/darksidelemm/alltheFSKs) - General FSK, not SAME-specific
- [dsame/dsame3](https://github.com/cuppa-joe/dsame) - Only parses already-demodulated messages

## Decision

Best path forward: Implement the DLL (Delay-Locked Loop) timing recovery from multimon-ng lines 328-349. This adjusts the phase based on bit transitions to keep sampling aligned with bit centers.

---

## Future Enhancements

### Multi-Protocol Support (Like multimon-ng)

**Status:** Architecture is well-positioned for generalization

The current decoder has excellent separation of concerns that would make multi-protocol support relatively straightforward:

**Layer 1 (FSK Demodulation) - Already Generic:**
- Correlation with I/Q templates
- DLL timing recovery
- Phase accumulator and integrator
- Sync pattern detection
- Byte assembly

**What's needed:** Extract to `FSKDemodulator` class with parameterized:
- Mark/space frequencies
- Baud rate
- Sync pattern
- Bit order (LSB/MSB)

**Layer 2 (Message Parsing) - Protocol-Specific:**
- SAME: `_process_decoded_byte()` understands ZCZC/NNNN structure
- Could be abstracted to `MessageParser` interface

**Potential Architecture:**
```python
class DigitalModeDecoder:
    def __init__(self, demodulator: FSKDemodulator,
                 parser: MessageParser):
        self.demod = demodulator
        self.parser = parser

    def process_audio_chunk(self, audio):
        bytes = self.demod.demodulate_fsk(audio, use_state=True)
        messages = []
        for byte_val in bytes:
            msg = self.parser.process_byte(byte_val)
            if msg:
                messages.append(msg)
        return messages

# Usage examples:
same = DigitalModeDecoder(
    FSKDemodulator(mark=2083.33, space=1562.5, baud=520.83),
    SAMEParser()
)

pocsag = DigitalModeDecoder(
    FSKDemodulator(mark=1200, space=1800, baud=512),
    POCSAGParser()
)

aprs = DigitalModeDecoder(
    FSKDemodulator(mark=1200, space=2200, baud=1200),
    APRSParser()
)
```

**Supported Protocols (with refactor):**
- ✅ SAME/EAS (current)
- 📟 POCSAG (pagers)
- 📻 APRS (packet radio)
- 📠 RTTY
- 🔊 AFSK modes
- Any FSK-based digital mode

**Effort estimate:** 2-3 days
- Extract FSK core → `FSKDemodulator` class
- Create `MessageParser` ABC
- Move SAME logic → `SAMEParser` implementation
- Add protocol registration/discovery

**Benefits:**
- Single codebase for multiple protocols
- Shared DLL/correlation optimizations
- Streaming works for all protocols
- Pure Python (no external dependencies)
