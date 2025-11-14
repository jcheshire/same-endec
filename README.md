# SAME Encoder/Decoder Web Application

Web application for encoding and decoding Emergency Alert System (EAS) messages using the SAME (Specific Area Message Encoding) protocol.

## Project Status

**Current Progress:**
- ✅ Backend API complete (FastAPI)
- ✅ Encoder module refactored and secured
- ✅ Decoder wrapper implemented
- ✅ Security vulnerabilities fixed
- ✅ Frontend complete (vanilla JS/CSS)
- ✅ Automated deployment script
- ⬜ multimon-ng compilation (run deploy.sh on Ubuntu)

## Project Structure

```
same-endec/
├── backend/
│   ├── encoder.py          # SAME protocol encoder (Python)
│   ├── decoder.py          # Wrapper for multimon-ng binary
│   ├── api.py              # FastAPI web server
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── index.html          # Web interface
│   ├── app.js              # Frontend logic (vanilla JS)
│   └── style.css           # Styling (no external dependencies)
├── multimon-ng/            # Decoder source code (C)
├── bin/                    # Compiled binaries go here
├── deploy.sh               # Automated deployment script
├── same_encoder.py         # Original encoder script (reference)
└── README.md
```

## How It Works

### Encoder (Python)
- Generates FSK-modulated WAV audio files from SAME message strings
- Uses AFSK with mark frequency (2083.33 Hz) and space frequency (1562.5 Hz)
- Encodes at 520.83 baud, outputs 43,750 Hz sample rate WAV
- Transmits messages 3x with preamble per SAME protocol spec

### Decoder (multimon-ng wrapper)
- Calls compiled multimon-ng binary via subprocess
- Parses JSON or text output
- Validates WAV files before processing
- Handles temp file management securely

### API Endpoints

- `POST /api/encode` - Build and encode SAME message → WAV file
- `POST /api/encode/raw` - Encode custom SAME string → WAV file
- `POST /api/encode/preview` - Preview SAME string without encoding
- `POST /api/decode` - Upload WAV → decoded SAME message
- `GET /api/event-codes` - List of EAS event codes
- `GET /api/fips-lookup/{code}` - Location code lookup

## Getting Started

### Prerequisites

**On Mac (for development):**
```bash
python3 --version  # Need Python 3.8+
```

**On Ubuntu (for deployment):**
```bash
# Will need to compile multimon-ng binary
sudo apt-get install build-essential cmake libpulse-dev
```

### Installation

#### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Dependencies:**
- fastapi - Web framework
- uvicorn - ASGI server
- numpy, scipy - Signal processing
- python-multipart - File uploads
- slowapi - Rate limiting
- pydantic - Request validation

#### 2. Compile multimon-ng (Ubuntu only)

**Important:** The multimon-ng binary must be compiled on Ubuntu, not Mac.

```bash
cd multimon-ng
mkdir build
cd build
cmake ..
make
cp multimon-ng ../../bin/
```

For Mac development, you can mock the decoder or skip decode testing until deploying to Ubuntu.

### Running the Application

#### Start the Backend API

```bash
cd backend
python api.py
```

Server runs at: `http://localhost:8000`

API docs (Swagger UI): `http://localhost:8000/docs`

#### Environment Variables

```bash
# Configure CORS allowed origins (comma-separated)
export ALLOWED_ORIGINS="http://localhost:3000,http://yoursite.com"
```

## Security Features

All OWASP Top 10 vulnerabilities addressed:

- ✅ Path traversal prevention
- ✅ Command injection protection
- ✅ Input validation (regex patterns)
- ✅ File upload size limits (10MB)
- ✅ WAV header validation (magic bytes)
- ✅ Rate limiting (5-20 req/min per endpoint)
- ✅ CORS restrictions (configurable origins)
- ✅ Error message sanitization
- ✅ Secure temp file handling

## Testing the API

### Encode a Message

```bash
curl -X POST http://localhost:8000/api/encode \
  -H "Content-Type: application/json" \
  -d '{
    "event_code": "TOR",
    "location_codes": ["024031"],
    "duration": "+0030",
    "originator": "SCIENCE"
  }' \
  --output test.wav
```

### Preview a Message

```bash
curl -X POST http://localhost:8000/api/encode/preview \
  -H "Content-Type: application/json" \
  -d '{
    "event_code": "TOR",
    "location_codes": ["024031"],
    "duration": "+0030"
  }'
```

### Decode a WAV File

```bash
curl -X POST http://localhost:8000/api/decode \
  -F "file=@test.wav"
```

### Get Event Codes

```bash
curl http://localhost:8000/api/event-codes
```

## Deployment

### Quick Start with Nginx (Recommended)

For production deployment with nginx reverse proxy:

```bash
# On Ubuntu server
git clone <your-repo-url>
cd same-endec

# Edit deploy.sh and set USE_NGINX=true
nano deploy.sh  # Change line 21: USE_NGINX=true

# Run deployment
sudo ./deploy.sh
```

**After deployment:**
1. Edit nginx config: `sudo nano /etc/nginx/sites-available/same-endec`
2. Replace `server_name _;` with your domain (e.g., `server_name same.example.com;`)
3. Test: `sudo nginx -t`
4. Reload: `sudo systemctl reload nginx`
5. Secure with Let's Encrypt: `sudo certbot --nginx -d your-domain.com`

### Automated Deployment Options

The `deploy.sh` script supports two modes:

**Option 1: With Nginx (Production)**
- Set `USE_NGINX=true` in deploy.sh (line 21)
- Installs nginx, configures reverse proxy
- Backend only listens on localhost (more secure)
- Single port 80/443 for everything
- No CORS issues

**Option 2: Without Nginx (Development/Testing)**
- Set `USE_NGINX=false` in deploy.sh (line 21, default)
- Runs separate frontend service on port 8080
- Backend on port 8000
- Good for development/testing

Both modes:
1. Install system dependencies (build tools, cmake, Python)
2. Set up Python virtual environment
3. Compile multimon-ng binary
4. Create systemd services
5. Enable auto-start on system reboot
6. Start services

### Manual Deployment

If you prefer manual setup:

#### 1. Install Dependencies
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv build-essential cmake libpulse-dev
```

#### 2. Set Up Python Environment
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. Compile multimon-ng
```bash
cd multimon-ng
mkdir build && cd build
cmake ..
make
cp multimon-ng ../../bin/
```

#### 4a. Run with Nginx (Production)
```bash
# Install and configure nginx
sudo apt-get install -y nginx
sudo cp nginx.conf /etc/nginx/sites-available/same-endec
sudo ln -s /etc/nginx/sites-available/same-endec /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Update server_name in config
sudo nano /etc/nginx/sites-available/same-endec

# Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx

# Start backend (binds to localhost only)
cd backend
source venv/bin/activate
python api.py
```

#### 4b. Run without Nginx (Development)
```bash
# Terminal 1 - Backend (public access for testing)
cd backend
source venv/bin/activate
python api.py --public

# Terminal 2 - Frontend
cd frontend
python3 -m http.server 8080
```

### Service Management

After running `deploy.sh`, services are managed via systemd:

```bash
# View logs
sudo journalctl -u same-endec-backend -f
sudo journalctl -u same-endec-frontend -f

# Restart services
sudo systemctl restart same-endec-backend
sudo systemctl restart same-endec-frontend

# Stop services
sudo systemctl stop same-endec-{backend,frontend}

# Start services
sudo systemctl start same-endec-{backend,frontend}

# Check status
sudo systemctl status same-endec-backend
sudo systemctl status same-endec-frontend
```

Services will automatically start on system reboot.

## Future Enhancements

- Add FIPS code database lookup
- Message history/logging
- Audio visualization (waveform/spectrogram)
- Batch processing
- WebSocket support for real-time updates
- Nginx reverse proxy configuration

## SAME Message Format

```
ZCZC-ORG-EEE-PSSCCC-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-
```

Where:
- `ZCZC` = Header (always)
- `ORG` = Originator (WXR, PEP, CIV)
- `EEE` = Event code (TOR, SVR, etc.)
- `PSSCCC` = Location code (6 digits, can repeat)
- `+TTTT` = Duration (+HHMM format)
- `JJJHHMM` = Timestamp (Julian day + time)
- `LLLLLLLL` = Originator callsign (8 chars max)

**Example:**
```
ZCZC-WXR-TOR-024031+0030-3171500-SCIENCE-
```
= Tornado warning for Montgomery County MD, valid 30 minutes

## Common Event Codes

- `TOR` - Tornado Warning
- `SVR` - Severe Thunderstorm Warning
- `EAN` - Emergency Action Notification
- `RWT` - Required Weekly Test
- `RMT` - Required Monthly Test

(Full list available via `/api/event-codes`)

## Troubleshooting

### "multimon-ng binary not found"
- Binary hasn't been compiled yet
- Must compile on Ubuntu (not Mac)
- Check `bin/multimon-ng` exists and is executable

### "Encoding failed"
- Check message length (max 268 chars)
- Validate SAME format
- Ensure location codes are 6 digits
- Duration must be +HHMM format

### Rate limit exceeded
- Wait 1 minute between requests
- Adjust limits in `api.py` if needed

## Development Notes

- Encoder outputs at 43,750 Hz sample rate
- Decoder expects 22,050 Hz input (multimon-ng spec)
- May need resampling layer for round-trip encoding/decoding
- Original script in `same_encoder.py` kept for reference
- Security fixes applied 2024-11-13

## License

Based on:
- Original encoder: Custom implementation
- multimon-ng: GPL v2.0

## References

- [SAME Protocol Specification](http://www.nws.noaa.gov/nwr/nwrsame.htm)
- [multimon-ng Documentation](https://github.com/EliasOenal/multimon-ng)
