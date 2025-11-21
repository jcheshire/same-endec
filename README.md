# SAME Encoder/Decoder Web Application

Web application for encoding and decoding Emergency Alert System (EAS) messages using the SAME (Specific Area Message Encoding) protocol.

## 🚀 Quick Start (TL;DR)

Want to run this on your server? It's simple:

```bash
# Clone the repository
git clone <your-repo-url>
cd same-endec

# Run the automated deployment script
sudo ./deploy.sh

# Optional: Add HTTPS with Let's Encrypt
sudo certbot --nginx -d your-domain.com
```

That's it! The deployment script will:
- Install all dependencies (Python, build tools, nginx, sox)
- Compile multimon-ng decoder
- Set up Python virtual environment
- Initialize FIPS county database
- Create systemd services that start on boot
- Configure nginx as a reverse proxy

Access your application at `http://your-server-ip` (or `https://your-domain.com` after adding SSL).

---

## Features

### Encoding
- **Build SAME Messages** - User-friendly form with event codes, county search, and duration dropdown
- **County Subdivision Support** - Select specific portions of counties (NW, N, NE, W, C, E, SW, S, SE) per 47 CFR § 11.31
  - **Text search:** Select county, then choose whole county or specific subdivisions
  - **Numeric search:** Enter 6-digit FIPS codes directly (e.g., 124031 for Northwest Montgomery County)
  - **Multi-select:** Pick multiple subdivisions of the same county for targeted alerts
  - **Visual distinction:** Blue tags for whole counties, amber tags for subdivisions
- **Smart County Search** - Search 3,143+ US counties by name or FIPS code with autocomplete
- **Duration Dropdown** - Pre-populated time increments (15-min up to 1hr, 30-min beyond) prevent format errors
- **Callsign Field** - Optional station identifier (defaults to PHILLYWX if empty)
- **Raw Encoding** - Encode custom SAME strings directly for advanced users
- **Automatic Preview** - SAME message string displayed with encoded audio
- **Unique Filenames** - Downloads timestamped WAV files (e.g., same_TOR_20241121_143022.wav)
- **Header and EOM Output** - Provides SAME header tones and End of Message audio
- **Protocol Compliance** - Validates duration increments and uses UTC timestamps per 47 CFR § 11.31

### Decoding
- **Upload WAV Files** - Decode SAME messages from audio
- **Human-Readable Output** - Location names with subdivisions, readable durations, full timestamps
- **Robust Parsing** - Handles noisy/partial messages gracefully
- **FIPS Lookup** - Automatically resolves county codes to names and subdivision descriptions

### Security
- **XSS Protection** - HTML escaping + Content Security Policy headers
- **SQL Injection Protection** - Parameterized queries throughout
- **Rate Limiting** - 5-20 requests/minute per endpoint
- **Input Validation** - Pydantic models with regex patterns
- **File Upload Security** - Size limits, magic byte validation, content-type checks
- **Command Injection Protection** - Subprocess list format, no shell execution

---

## Project Structure

```
same-endec/
├── backend/
│   ├── encoder.py          # SAME protocol encoder
│   ├── decoder.py          # multimon-ng wrapper
│   ├── api.py              # FastAPI web server
│   ├── init_fips_db.py     # FIPS database initialization
│   ├── generate_eom.py     # Static EOM WAV generator
│   ├── requirements.txt    # Python dependencies
│   └── fips_codes.db       # SQLite database (3,143 counties)
├── frontend/
│   ├── index.html          # Main web interface (encode/decode)
│   ├── reference.html      # SAME protocol reference documentation
│   ├── app.js              # Frontend logic (vanilla JS)
│   ├── style.css           # Emergency alert themed styling
│   └── eom.wav             # Static End of Message audio
├── multimon-ng/            # Decoder source (from https://github.com/EliasOenal/multimon-ng)
├── bin/                    # Compiled binaries (created by deploy.sh)
│   └── multimon-ng         # Decoder binary
├── deploy.sh               # Automated deployment script
└── README.md
```

---

## How It Works

### SAME Encoder (Python)
- Generates FSK-modulated WAV audio from SAME message strings
- Uses AFSK with mark frequency 2083.33 Hz and space frequency 1562.5 Hz
- Encodes at 520.83 baud, outputs 44.1 kHz sample rate WAV
- Transmits header 3 times with preamble per SAME protocol spec
- Outputs separate header and EOM files for flexible audio production

### SAME Decoder (multimon-ng wrapper)
- Calls compiled multimon-ng binary via subprocess
- Parses JSON output with robust error handling
- Validates WAV files before processing (magic bytes)
- Cleans noisy messages and handles partial data
- Enriches output with human-readable information

### Web Frontend (Vanilla JS)
- Zero external dependencies (no React, Vue, jQuery, etc.)
- County autocomplete search using FIPS database API
- Real-time validation and preview
- Audio player with download functionality
- Emergency alert theme with amber accents
- Responsive design for mobile and desktop (narrower 800px container)
- Separate reference documentation page

### API Endpoints

#### Encoding
- `POST /api/encode` - Build and encode SAME message → Header WAV
- `POST /api/encode/raw` - Encode custom SAME string → Header WAV
- `POST /api/encode/preview` - Preview SAME string without encoding

#### Decoding
- `POST /api/decode` - Upload WAV → enriched decoded message

#### Reference Data
- `GET /api/event-codes` - List of 50+ EAS event codes
- `GET /api/fips-search?q=<county>` - Search counties by name
- `GET /api/fips-lookup/{code}` - Look up county by FIPS code

#### Health
- `GET /health` - Health check endpoint

---

## Installation & Deployment

### Prerequisites

**Operating System:** Ubuntu 20.04+ or Debian 11+ (for deployment)

**System Packages:**
- Python 3.8+
- build-essential, cmake (for compiling multimon-ng)
- libpulse-dev, sox (for audio processing)
- nginx (optional, for production)

### Automated Deployment (Recommended)

The `deploy.sh` script handles everything:

```bash
# Clone repository
git clone <your-repo-url>
cd same-endec

# Run deployment script
sudo ./deploy.sh
```

The script will:
1. ✅ Install system dependencies (Python, build tools, sox, nginx)
2. ✅ Create Python virtual environment
3. ✅ Install Python packages (FastAPI, numpy, scipy, etc.)
4. ✅ Download and initialize FIPS database (3,143 counties)
5. ✅ Generate static EOM WAV file
6. ✅ Compile multimon-ng decoder binary
7. ✅ Create systemd services for auto-start
8. ✅ Configure nginx reverse proxy
9. ✅ Start all services

**Configuration:**

By default, `deploy.sh` uses nginx. If you want to run without nginx:
```bash
# Edit deploy.sh
nano deploy.sh
# Change line 21: USE_NGINX=false

# Then run deployment
sudo ./deploy.sh
```

### Post-Deployment Setup

#### 1. Configure Domain Name (Optional)

Edit the nginx configuration:
```bash
sudo nano /etc/nginx/sites-available/same-endec
```

Replace `server_name _;` with your domain:
```nginx
server_name same.yourdomain.com;
```

Test and reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

#### 2. Add HTTPS with Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Obtain and install certificate
sudo certbot --nginx -d same.yourdomain.com

# Follow the prompts
# Choose option 2 to redirect HTTP → HTTPS
```

Certificates auto-renew via cron.

### Service Management

Services are managed via systemd:

```bash
# View logs (real-time)
sudo journalctl -u same-endec-backend -f

# Restart backend after code changes
sudo systemctl restart same-endec-backend

# Check service status
sudo systemctl status same-endec-backend

# Stop services
sudo systemctl stop same-endec-backend

# Start services
sudo systemctl start same-endec-backend

# Disable auto-start
sudo systemctl disable same-endec-backend
```

Services automatically start on system reboot.

### Manual Installation (Development)

For local development without systemd:

#### 1. Install Python Dependencies

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2. Initialize FIPS Database

```bash
python init_fips_db.py
```

#### 3. Generate EOM File

```bash
python generate_eom.py
```

#### 4. Run Backend

```bash
python api.py
```

Backend runs at: `http://localhost:8000`
API docs (Swagger): `http://localhost:8000/docs`

#### 5. Serve Frontend

```bash
# In a separate terminal
cd frontend
python3 -m http.server 8080
```

Frontend runs at: `http://localhost:8080`

---

## Environment Variables

Configure via environment variables or systemd service files:

```bash
# CORS allowed origins (comma-separated)
export ALLOWED_ORIGINS="http://localhost:8080,https://same.yourdomain.com"

# Backend bind address (default: 127.0.0.1 for nginx, 0.0.0.0 for standalone)
export BIND_HOST="127.0.0.1"

# Backend port (default: 8000)
export PORT="8000"
```

---

## Usage Examples

### Web Interface

1. Navigate to your deployed URL (e.g., `https://same.yourdomain.com`)
2. Select **Encode Message** tab
3. Choose an event code (e.g., "TOR - Tornado Warning")
4. Search and select counties (e.g., "Montgomery, MD")
   - For subdivisions: Select county, then choose specific regions (NW, N, NE, etc.) or whole county
5. Set duration (e.g., "30 minutes")
6. Optionally enter callsign (defaults to PHILLYWX)
7. Click **Encode to WAV**
8. View the encoded message string and download **Header** and **EOM** audio files

### API Usage

#### Encode a Message

```bash
curl -X POST http://localhost:8000/api/encode \
  -H "Content-Type: application/json" \
  -d '{
    "event_code": "TOR",
    "originator": "WXR",
    "location_codes": ["024031"],
    "duration": "+0030",
    "callsign": "SCIENCE"
  }' \
  --output header.wav
```

#### Preview a Message

```bash
curl -X POST http://localhost:8000/api/encode/preview \
  -H "Content-Type: application/json" \
  -d '{
    "event_code": "TOR",
    "originator": "WXR",
    "location_codes": ["024031"],
    "duration": "+0030"
  }'
```

Response:
```json
{
  "success": true,
  "message": "ZCZC-WXR-TOR-024031+0030-3191423-SCIENCE-"
}
```

#### Decode a WAV File

```bash
curl -X POST http://localhost:8000/api/decode \
  -F "file=@header.wav"
```

Response:
```json
{
  "success": true,
  "messages": [{
    "raw": "WXR-TOR-024031+0030-3191423-SCIENCE-",
    "parsed": {
      "org": "WXR",
      "org_description": "National Weather Service",
      "event": "TOR",
      "event_description": "Tornado Warning",
      "locations": ["024031"],
      "location_details": [{
        "fips": "024031",
        "name": "Montgomery County",
        "state": "MD"
      }],
      "duration": "+0030",
      "duration_readable": "30 minutes",
      "timestamp": "3191423",
      "timestamp_readable": "November 15, 2024 at 14:23 UTC",
      "originator": "SCIENCE"
    }
  }]
}
```

#### Search Counties

```bash
curl "http://localhost:8000/api/fips-search?q=Montgomery&limit=10"
```

---

## SAME Message Format

SAME messages follow this structure:

```
ZCZC-ORG-EEE-PSSCCC-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-
```

**Field Breakdown:**

| Field | Description | Example | Notes |
|-------|-------------|---------|-------|
| `ZCZC` | Header | ZCZC | Always present |
| `ORG` | Originator | WXR | 3 chars (WXR, PEP, CIV, EAS) |
| `EEE` | Event code | TOR | 3 chars (see event codes) |
| `PSSCCC` | Location code | 024031 | 6 digits (P=part, SS=state, CCC=county) |
| `+TTTT` | Duration | +0030 | +HHMM format |
| `JJJHHMM` | Timestamp | 3191423 | JJJ=Julian day, HHMM=UTC time |
| `LLLLLLLL` | Callsign | SCIENCE | Max 8 characters (optional) |

**Example Message:**
```
ZCZC-WXR-TOR-024031+0030-3191423-SCIENCE-
```

Translates to: *Tornado Warning from National Weather Service for Montgomery County, MD, valid for 30 minutes, issued on November 15 at 14:23 UTC, by station SCIENCE*

**Multiple Locations:**
```
ZCZC-WXR-TOR-024031-024033-024017+0030-3191423-SCIENCE-
```

Covers Montgomery, Prince George's, and Charles counties in Maryland.

---

## Common Event Codes

| Code | Description |
|------|-------------|
| `TOR` | Tornado Warning |
| `SVR` | Severe Thunderstorm Warning |
| `EAN` | Emergency Action Notification (National Emergency) |
| `EAT` | Emergency Action Termination |
| `NIC` | National Information Center |
| `NPT` | National Periodic Test |
| `RMT` | Required Monthly Test |
| `RWT` | Required Weekly Test |
| `FFW` | Flash Flood Warning |
| `EVI` | Evacuation Immediate |
| `CEM` | Civil Emergency Message |
| `CAE` | Child Abduction Emergency (AMBER Alert) |
| `HUW` | Hurricane Warning |
| `TSW` | Tsunami Warning |
| `EQW` | Earthquake Warning |

Full list of 50+ codes available via `/api/event-codes` endpoint or the Reference page.

---

## Troubleshooting

### Deployment Issues

**"multimon-ng binary not found"**
- Binary hasn't been compiled yet
- Must be compiled on Ubuntu/Debian (not macOS)
- Run `deploy.sh` to compile automatically
- Check that `bin/multimon-ng` exists and is executable

**"execlp: No such file or directory" when decoding**
- Sox is not installed or not in PATH
- Install: `sudo apt-get install sox`
- If using systemd, ensure PATH includes `/usr/bin` (deploy.sh handles this)

**Nginx 403 Forbidden**
- Frontend files not readable by nginx
- Check file permissions: `ls -la frontend/`
- If files are in user home directory, move to `/var/www/same-endec`
- Update nginx config `root` directive

**Services not starting on reboot**
- Services not enabled: `sudo systemctl enable same-endec-backend`
- Check logs: `sudo journalctl -u same-endec-backend`

### Encoding Issues

**"Message too long (max 268 chars)"**
- SAME protocol limits messages to 268 characters
- Reduce number of location codes
- Shorten callsign

**"Invalid duration format"**
- Duration must match `+HHMM` pattern
- Examples: `+0030` (30 min), `+0100` (1 hour), `+0015` (15 min)

**Location codes not found**
- FIPS database not initialized
- Run `python init_fips_db.py` in backend directory
- Or run `deploy.sh` which initializes automatically

### Decoding Issues

**"No SAME message detected"**
- Audio file doesn't contain valid SAME tones
- Audio quality too poor (noise, distortion)
- Wrong sample rate (should be 22050 Hz or higher)
- File is not a WAV file (check with `file <filename>`)

**Partial message warning**
- Audio cut off before end of message
- Noisy audio causing decode errors
- Decoder will extract whatever valid fields it can find

**Unknown county names**
- FIPS code not in database (rare)
- Or FIPS code is corrupted from noisy audio

### API Issues

**Rate limit exceeded**
- Wait 1 minute between requests
- Or adjust rate limits in `api.py` (lines with `@limiter.limit()`)

**CORS errors in browser**
- Frontend and backend on different domains without proper CORS setup
- Use nginx reverse proxy (recommended)
- Or add your domain to `ALLOWED_ORIGINS` environment variable

---

## Development Notes

### Audio Format Details
- **Encoder Output:** 44,100 Hz, 16-bit PCM WAV, mono
- **Decoder Input:** 22,050 Hz or higher (multimon-ng requirement)
- **FSK Modulation:** Mark 2083.33 Hz (binary 0), Space 1562.5 Hz (binary 1)
- **Baud Rate:** 520.83 baud (per SAME spec)

### FIPS Code Format
- **SAME Protocol:** 6-digit format `PSSCCC` (P=subdivision part, SS=state, CCC=county)
- **Database:** 5-digit format `SSCCC` (standard FIPS)
- **Conversion:** Leading zero stripped for database lookup

### Audio Output Format

The encoder provides two separate audio files:

1. **Header WAV** - Generated by `/api/encode` (contains SAME alert tones repeated 3x)
2. **EOM WAV** - Static file at `/eom.wav` (contains end-of-message "NNNN" repeated 3x)

Users can combine these with their own audio content as needed for their broadcasting workflow.

### Security Audit Results

**Overall Security Rating:** A (Excellent)

Addressed vulnerabilities:
- ✅ XSS via innerHTML (HTML escaping implemented)
- ✅ SQL injection (parameterized queries + security comments)
- ✅ Command injection (subprocess list format, path validation)
- ✅ Rate limiting on all endpoints
- ✅ CSP headers and security headers middleware
- ✅ File upload validation (size, magic bytes, content-type)
- ✅ Input validation with Pydantic regex patterns

No critical or high-severity vulnerabilities found.

---

## Architecture

### Backend (Python/FastAPI)
- **FastAPI Framework:** Modern async web framework
- **Pydantic Validation:** Type-safe request/response models
- **NumPy/SciPy:** Signal processing for FSK encoding
- **SQLite:** FIPS code database (3,143+ counties)
- **multimon-ng:** External C binary for decoding
- **slowapi:** Rate limiting middleware

### Frontend (Vanilla JavaScript)
- **Zero Dependencies:** No npm, webpack, React, jQuery, etc.
- **Progressive Enhancement:** Works without JavaScript for basic functionality
- **Responsive Design:** Mobile-first CSS with flexbox
- **Fetch API:** Modern async HTTP requests
- **HTML5 Audio:** Native audio playback

### Deployment
- **systemd:** Service management and auto-start
- **nginx:** Reverse proxy, static file serving, SSL termination
- **Let's Encrypt:** Free SSL certificates via certbot

---

## Contributing

This is a personal project but suggestions welcome:

1. Open an issue describing the bug/feature
2. Fork the repository
3. Create a feature branch
4. Make your changes with tests
5. Submit a pull request

---

## License

**Backend Code:** Custom implementation
**multimon-ng:** GPL v2.0 (from [EliasOenal/multimon-ng](https://github.com/EliasOenal/multimon-ng))
**FIPS Data:** Public domain (US Census Bureau)

---

## Development Status & Roadmap

### Current Status

The application is **fully functional** with core SAME encoding/decoding capabilities:

✅ **Core Features:**
- SAME message encoding and decoding
- County subdivision support with abbreviated labels (NW, N, NE, W, C, E, SW, S, SE)
- Streamlined county selection interface
- Smart county search (3,143+ US counties)
- Protocol-compliant duration validation and UTC timestamps
- Automated deployment with systemd and nginx
- Security hardening (XSS, SQL injection, rate limiting, etc.)
- Unique timestamped WAV filenames
- Separate reference documentation page
- Optional callsign field with automatic PHILLYWX default

### Feature Requests & Future Enhancements

These are planned improvements to enhance UX and add convenience features:

**User Experience:**
1. **Update raw SAME encode placeholder** - Include PHILLYWX in the example string instead of SCIENCE
2. **Better visual indicators** - Show selected subdivisions more clearly, possibly with interactive county map
3. **Enhanced toast notifications** - Improve styling, positioning, and animation

**Quality of Life:**
4. **Keyboard shortcuts** - Add hotkeys for common operations
5. **Message presets** - Export/import frequently used message templates
6. **County search optimization** - Cache search results for better performance
7. **End-to-end testing** - Comprehensive test suite for subdivision encoding/decoding with actual WAV files

### For Contributors/Future Sessions

**Key Files:**
- `backend/api.py` - FIPS search with subdivision support
- `backend/encoder.py` - Duration validation and UTC timestamps
- `frontend/app.js` - Subdivision selector logic (line ~538: `showSubdivisionSelector`)
- `frontend/style.css` - Subdivision selector styling
- `frontend/index.html` - Subdivision selector container

**Testing Subdivision Feature:**
1. Text search (e.g., "Montgomery") → county results displayed
2. Click county → subdivision selector appears in cream-colored box
3. Choose "Whole County" checkbox or select specific subdivisions (NW, N, NE, W, C, E, SW, S, SE)
4. Click "Add Selected" → adds to counties list with subdivision codes
5. Numeric search (e.g., "124031") → bypasses selector, adds directly

**Subdivision Code Format:**
- Leading digit 1-9 = subdivision (0 = whole county)
- Format: `PSSCCC` where P=part, SS=state FIPS, CCC=county FIPS
- Example: `124031` = Northwest (1) Montgomery County (24031), MD

---

## References

- [SAME Protocol Specification (NOAA)](http://www.nws.noaa.gov/nwr/nwrsame.htm)
- [47 CFR § 11.31 - EAS Protocol](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-11/subpart-B/section-11.31)
- [multimon-ng GitHub](https://github.com/EliasOenal/multimon-ng)
- [EAS Wikipedia](https://en.wikipedia.org/wiki/Emergency_Alert_System)
- [FIPS County Codes](https://www.census.gov/library/reference/code-lists/ansi.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
