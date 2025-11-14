"""
FastAPI Backend for SAME Encoder/Decoder Web Application
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uvicorn
import logging
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from encoder import SAMEEncoder, build_same_message
from decoder import SAMEDecoder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure rate limiting
limiter = Limiter(key_func=get_remote_address)

# Database configuration
DB_PATH = os.path.join(os.path.dirname(__file__), 'fips_codes.db')

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


app = FastAPI(
    title="SAME Encoder/Decoder API",
    description="Web API for encoding and decoding EAS SAME protocol messages",
    version="1.0.0"
)

# Add rate limiting to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware to allow frontend access
# Security: Configure allowed origins. For development, using localhost.
# In production, replace with your actual domain(s)
import os
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only allow needed methods
    allow_headers=["Content-Type", "Authorization"],
)

# Initialize encoder and decoder
encoder = SAMEEncoder()
decoder = SAMEDecoder()


# Pydantic models for request validation
class EncodeRequest(BaseModel):
    """Request model for encoding a SAME message"""
    event_code: str = Field(..., min_length=3, max_length=3, description="3-letter event code (e.g., TOR, SVR, RWT)")
    location_codes: List[str] = Field(..., min_items=1, max_items=31, description="List of 6-digit FIPS location codes")
    duration: str = Field(..., pattern=r'^\+\d{4}$', description="Duration in +HHMM format (e.g., +0030)")
    timestamp: Optional[str] = Field(None, pattern=r'^\d{7}$', description="Optional JJJHHMM timestamp")
    originator: str = Field("SCIENCE", min_length=1, max_length=8, description="Originator callsign/identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "event_code": "TOR",
                "location_codes": ["024031"],
                "duration": "+0030",
                "timestamp": None,
                "originator": "SCIENCE"
            }
        }


class EncodeRawRequest(BaseModel):
    """Request model for encoding a raw SAME string"""
    same_string: str = Field(..., min_length=1, max_length=268, description="Complete SAME format string")

    class Config:
        json_schema_extra = {
            "example": {
                "same_string": "ZCZC-WXR-TOR-024031+0030-3171500-SCIENCE-"
            }
        }


class MessageResponse(BaseModel):
    """Response model for successfully encoded message"""
    success: bool
    same_string: str
    message: str


# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "SAME Encoder/Decoder API",
        "version": "1.0.0"
    }


@app.post("/api/encode", response_class=Response)
@limiter.limit("10/minute")
async def encode_message(request: Request, encode_request: EncodeRequest):
    """
    Encode a SAME message and return WAV audio file

    Returns the WAV file as audio/wav binary data
    """
    try:
        # Build SAME message string
        same_string = build_same_message(
            event_code=encode_request.event_code,
            location_codes=encode_request.location_codes,
            duration=encode_request.duration,
            timestamp=encode_request.timestamp,
            originator=encode_request.originator
        )

        # Encode to WAV bytes (header only, no EOM)
        wav_data = encoder.encode(same_string, include_eom=False)

        # Return as downloadable WAV file
        return Response(
            content=wav_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename=same_{encode_request.event_code}_header.wav"
            }
        )

    except ValueError as e:
        # Input validation errors - safe to expose
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected errors - log details but return generic message
        logger.error(f"Encoding failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Encoding failed due to server error")


@app.post("/api/encode/raw", response_class=Response)
@limiter.limit("10/minute")
async def encode_raw_message(request: Request, encode_request: EncodeRawRequest):
    """
    Encode a raw SAME string and return WAV audio file

    Accepts a pre-formatted SAME string (e.g., "ZCZC-WXR-TOR-024031+0030-3171500-SCIENCE-")
    Returns the WAV file as audio/wav binary data
    """
    try:
        # Encode to WAV bytes (header only, no EOM)
        wav_data = encoder.encode(encode_request.same_string, include_eom=False)

        # Return as downloadable WAV file
        return Response(
            content=wav_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=same_custom_header.wav"
            }
        )

    except ValueError as e:
        # Input validation errors - safe to expose
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected errors - log details but return generic message
        logger.error(f"Raw encoding failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Encoding failed due to server error")


@app.post("/api/encode/preview")
@limiter.limit("20/minute")
async def encode_preview(request: Request, encode_request: EncodeRequest):
    """
    Preview the SAME string that would be generated (without encoding audio)

    Useful for validating message format before encoding
    """
    try:
        same_string = build_same_message(
            event_code=encode_request.event_code,
            location_codes=encode_request.location_codes,
            duration=encode_request.duration,
            timestamp=encode_request.timestamp,
            originator=encode_request.originator
        )

        return MessageResponse(
            success=True,
            same_string=same_string,
            message=f"Message preview: {same_string}"
        )

    except ValueError as e:
        # Input validation errors - safe to expose
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected errors - log details but return generic message
        logger.error(f"Preview failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Preview failed due to server error")


def enrich_parsed_message(parsed: Dict) -> Dict:
    """
    Enrich a parsed SAME message with human-readable information

    Args:
        parsed: Dictionary with parsed SAME components

    Returns:
        Dictionary with enriched data including location names, readable duration, etc.
    """
    enriched = parsed.copy()

    # Decode event code
    event_codes = get_event_codes_dict()
    if parsed.get("event"):
        enriched["event_description"] = event_codes.get(parsed["event"], "Unknown Event")

    # Decode originator
    originators = {
        "WXR": "National Weather Service",
        "PEP": "Primary Entry Point",
        "CIV": "Civil Authority",
        "EAS": "EAS Participant"
    }
    if parsed.get("org"):
        enriched["org_description"] = originators.get(parsed["org"], parsed["org"])

    # Decode locations using FIPS database
    if parsed.get("locations"):
        location_details = []
        conn = get_db()
        cursor = conn.cursor()
        for fips in parsed["locations"]:
            # Pad to 6 digits
            fips_padded = fips.zfill(6)
            cursor.execute('SELECT name, state FROM fips_codes WHERE fips = ? AND type = "county"', (fips_padded,))
            row = cursor.fetchone()
            if row:
                location_details.append({
                    "fips": fips_padded,
                    "name": row['name'],
                    "state": row['state']
                })
            else:
                location_details.append({
                    "fips": fips_padded,
                    "name": "Unknown",
                    "state": "Unknown"
                })
        conn.close()
        enriched["location_details"] = location_details

    # Decode duration
    if parsed.get("duration"):
        try:
            # Duration format: +HHMM
            duration_str = parsed["duration"].lstrip('+')
            hours = int(duration_str[:2])
            minutes = int(duration_str[2:4])
            total_minutes = hours * 60 + minutes

            if hours > 0 and minutes > 0:
                enriched["duration_readable"] = f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
            elif hours > 0:
                enriched["duration_readable"] = f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                enriched["duration_readable"] = f"{minutes} minute{'s' if minutes != 1 else ''}"

            enriched["duration_minutes"] = total_minutes
        except (ValueError, IndexError):
            pass

    # Decode timestamp (Julian day + time)
    if parsed.get("timestamp"):
        try:
            timestamp_str = parsed["timestamp"]
            if len(timestamp_str) == 7:
                julian_day = int(timestamp_str[:3])
                hour = int(timestamp_str[3:5])
                minute = int(timestamp_str[5:7])

                # Get current year to calculate date from Julian day
                current_year = datetime.now(timezone.utc).year
                date = datetime(current_year, 1, 1, tzinfo=timezone.utc) + \
                       timedelta(days=julian_day - 1, hours=hour, minutes=minute)

                enriched["timestamp_readable"] = date.strftime("%B %d, %Y at %H:%M UTC")
                enriched["timestamp_iso"] = date.isoformat()
        except (ValueError, IndexError):
            pass

    return enriched


def get_event_codes_dict() -> Dict[str, str]:
    """Get event codes as a dictionary"""
    return {
        "TOR": "Tornado Warning",
        "SVR": "Severe Thunderstorm Warning",
        "EAN": "Emergency Action Notification",
        "EAT": "Emergency Action Termination",
        "NIC": "National Information Center",
        "NPT": "National Periodic Test",
        "RMT": "Required Monthly Test",
        "RWT": "Required Weekly Test",
        "TOE": "911 Telephone Outage Emergency",
        "ADR": "Administrative Message",
        "AVW": "Avalanche Warning",
        "AVA": "Avalanche Watch",
        "BZW": "Blizzard Warning",
        "CAE": "Child Abduction Emergency",
        "CDW": "Civil Danger Warning",
        "CEM": "Civil Emergency Message",
        "CFW": "Coastal Flood Warning",
        "CFA": "Coastal Flood Watch",
        "DSW": "Dust Storm Warning",
        "EQW": "Earthquake Warning",
        "EVI": "Evacuation Immediate",
        "FRW": "Fire Warning",
        "FFW": "Flash Flood Warning",
        "FFA": "Flash Flood Watch",
        "FFS": "Flash Flood Statement",
        "FLW": "Flood Warning",
        "FLA": "Flood Watch",
        "FLS": "Flood Statement",
        "HMW": "Hazardous Materials Warning",
        "HUW": "Hurricane Warning",
        "HUA": "Hurricane Watch",
        "HWW": "High Wind Warning",
        "HWA": "High Wind Watch",
        "LAE": "Local Area Emergency",
        "LEW": "Law Enforcement Warning",
        "NAT": "National Audible Test",
        "NMN": "Network Message Notification",
        "SPW": "Shelter in Place Warning",
        "SMW": "Special Marine Warning",
        "SPS": "Special Weather Statement",
        "SSA": "Storm Surge Watch",
        "SSW": "Storm Surge Warning",
        "TOA": "Tornado Watch",
        "TRW": "Tropical Storm Warning",
        "TRA": "Tropical Storm Watch",
        "TSW": "Tsunami Warning",
        "TSA": "Tsunami Watch",
        "VOW": "Volcano Warning",
        "WSW": "Winter Storm Warning",
        "WSA": "Winter Storm Watch"
    }


@app.post("/api/decode")
@limiter.limit("5/minute")
async def decode_message(request: Request, file: UploadFile = File(...)):
    """
    Decode a WAV file containing SAME encoded message

    Upload a WAV file and receive decoded SAME message data
    """
    # Security: Validate file extension
    if not file.filename or not file.filename.lower().endswith('.wav'):
        raise HTTPException(status_code=400, detail="File must be a WAV file")

    # Security: Validate content type
    if file.content_type and file.content_type not in ['audio/wav', 'audio/x-wav', 'audio/wave']:
        raise HTTPException(status_code=400, detail="Invalid content type. Must be audio/wav")

    try:
        # Security: Read with size limit (10MB max)
        MAX_SIZE = 10 * 1024 * 1024
        wav_data = await file.read(MAX_SIZE + 1)

        if len(wav_data) > MAX_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large (max {MAX_SIZE // 1024 // 1024}MB)")

        # Decode using multimon-ng
        result = decoder.decode_bytes(wav_data, use_json=True)

        if not result["success"]:
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "message": "No SAME message detected in audio file",
                    "raw_output": result["raw_output"]
                }
            )

        # Parse and enrich decoded messages
        parsed_messages = []
        for msg in result["messages"]:
            if "last_message" in msg:
                parsed = decoder.parse_same_message(msg["last_message"])
                enriched = enrich_parsed_message(parsed)
                parsed_messages.append({
                    "raw": msg["last_message"],
                    "parsed": enriched
                })

        return {
            "success": True,
            "messages": parsed_messages,
            "end_of_message": result["end_of_message"],
            "count": len(parsed_messages)
        }

    except ValueError as e:
        # Input validation errors - safe to expose
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        # Binary not found - safe to expose
        raise HTTPException(status_code=503, detail="Decoder service unavailable")
    except Exception as e:
        # Unexpected errors - log details but return generic message
        logger.error(f"Decoding failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Decoding failed due to server error")


@app.get("/api/event-codes")
async def get_event_codes():
    """
    Get list of common EAS event codes with descriptions
    """
    # Return as simple key-value pairs for frontend dropdown
    return get_event_codes_dict()


@app.get("/api/fips-search")
@limiter.limit("20/minute")
async def fips_search(request: Request, q: str = "", state: str = "", limit: int = 20):
    """
    Search for FIPS codes by county/location name

    Query parameters:
    - q: Search query (county name)
    - state: Filter by state code (e.g., "MD", "CA")
    - limit: Max results (default 20, max 100)
    """
    # Security: Validate inputs
    if limit > 100:
        limit = 100

    if len(q) < 2 and not state:
        return {"results": [], "count": 0}

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Build query
        sql = 'SELECT fips, name, state, type FROM fips_codes WHERE type = "county"'
        params = []

        if q:
            sql += ' AND name LIKE ?'
            params.append(f'%{q}%')

        if state:
            sql += ' AND state = ?'
            params.append(state.upper())

        sql += ' ORDER BY name LIMIT ?'
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        results = [
            {
                "fips": row['fips'],
                "name": row['name'],
                "state": row['state'],
                "display": f"{row['name']}, {row['state']} ({row['fips']})"
            }
            for row in rows
        ]

        return {
            "results": results,
            "count": len(results),
            "query": q,
            "state_filter": state
        }

    except Exception as e:
        logger.error(f"FIPS search failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="FIPS search failed")


@app.get("/api/fips-lookup/{code}")
async def fips_lookup(code: str):
    """
    Look up FIPS code information from database

    Returns county/location information for a given FIPS code
    """
    # Security: Validate FIPS code format (should be 4-6 digits)
    if not code.isdigit() or len(code) < 1 or len(code) > 6:
        raise HTTPException(status_code=400, detail="Invalid FIPS code format")

    # Pad to 4 digits for county codes (e.g., "1001" not "11001")
    # SAME protocol uses PSSCCC format where PSS is state and CCC is county
    if len(code) == 5:
        # Convert 5-digit to 4-digit (remove leading digit if it's a 0)
        code = code.lstrip('0') or '0'

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Look up FIPS code
        cursor.execute(
            'SELECT fips, name, state, type FROM fips_codes WHERE fips = ?',
            (code.zfill(4),)  # Pad with leading zeros to 4 digits
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "code": code,
                "fips": row['fips'],
                "location": row['name'],
                "state": row['state'],
                "type": row['type'],
                "found": True
            }
        else:
            return {
                "code": code,
                "location": "Unknown",
                "found": False
            }

    except Exception as e:
        logger.error(f"FIPS lookup failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="FIPS lookup failed")


if __name__ == "__main__":
    # Run the API server
    # Security: Bind to 127.0.0.1 when behind nginx reverse proxy
    # Use 0.0.0.0 for direct access (development/testing)
    import sys

    # Check if --public flag is passed for direct access
    if "--public" in sys.argv:
        host = "0.0.0.0"
        print("WARNING: Running with public access (0.0.0.0)")
        print("Use nginx reverse proxy for production deployment")
    else:
        host = "127.0.0.1"
        print("Running on localhost only (127.0.0.1)")
        print("Accessible via nginx reverse proxy or direct local access")

    uvicorn.run(
        "api:app",
        host=host,
        port=8000,
        reload=True
    )
