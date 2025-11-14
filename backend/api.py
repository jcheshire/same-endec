"""
FastAPI Backend for SAME Encoder/Decoder Web Application
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn
import logging
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

        # Encode to WAV bytes
        wav_data = encoder.encode(same_string)

        # Return as downloadable WAV file
        return Response(
            content=wav_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename=same_{encode_request.event_code}.wav"
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
        # Encode to WAV bytes
        wav_data = encoder.encode(encode_request.same_string)

        # Return as downloadable WAV file
        return Response(
            content=wav_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=same_custom.wav"
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

        # Parse decoded messages
        parsed_messages = []
        for msg in result["messages"]:
            if "last_message" in msg:
                parsed = decoder.parse_same_message(msg["last_message"])
                parsed_messages.append({
                    "raw": msg["last_message"],
                    "parsed": parsed
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
    event_codes = {
        "TOR": "Tornado Warning",
        "SVR": "Severe Thunderstorm Warning",
        "FFW": "Flash Flood Warning",
        "EVI": "Evacuation Immediate",
        "EAN": "Emergency Action Notification",
        "EAT": "Emergency Action Termination",
        "NIC": "National Information Center",
        "NPT": "National Periodic Test",
        "RMT": "Required Monthly Test",
        "RWT": "Required Weekly Test",
        "ADR": "Administrative Message",
        "AVW": "Avalanche Warning",
        "BZW": "Blizzard Warning",
        "CAE": "Child Abduction Emergency",
        "CDW": "Civil Danger Warning",
        "CEM": "Civil Emergency Message",
        "CFA": "Coastal Flood Watch",
        "CFW": "Coastal Flood Warning",
        "DMO": "Demo Warning",
        "DSW": "Dust Storm Warning",
        "EQW": "Earthquake Warning",
        "EWW": "Extreme Wind Warning",
        "FRW": "Fire Warning",
        "HMW": "Hazardous Materials Warning",
        "HUW": "Hurricane Warning",
        "LEW": "Law Enforcement Warning",
        "NAT": "National Audible Test",
        "NMN": "Network Message Notification",
        "NUW": "Nuclear Power Plant Warning",
        "SPW": "Shelter in Place Warning",
        "TOE": "911 Outage Emergency",
        "TSW": "Tsunami Warning",
        "VOW": "Volcano Warning"
    }

    # Return as simple key-value pairs for frontend dropdown
    return event_codes


@app.get("/api/fips-lookup/{code}")
async def fips_lookup(code: str):
    """
    Look up FIPS code information (placeholder - would need real database)
    """
    # This is a placeholder. In production, integrate with a FIPS code database
    common_codes = {
        "000000": "United States (All)",
        "024031": "Montgomery County, MD",
        "011001": "District of Columbia",
    }

    if code in common_codes:
        return {
            "code": code,
            "location": common_codes[code],
            "found": True
        }
    else:
        return {
            "code": code,
            "location": "Unknown",
            "found": False
        }


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
