from fastapi import APIRouter, Request, HTTPException, Header
from datetime import datetime
import os
import hashlib
import hmac
import json
import httpx

router = APIRouter()

HOS_BRIDGE_KEY = os.getenv("HOS_BRIDGE_KEY")
INTERNAL_API_URL = os.getenv("INTERNAL_API_URL", "http://localhost:8000")
MANIFEST_SUBMIT_ROUTE = "/manifest/submit"

async def submit_internal_manifest(payload: dict):
   """Submit a verified payload to the internal manifest route."""
   try:
       async with httpx.AsyncClient(base_url=INTERNAL_API_URL) as client:
           print(f"Initiating internal relay to: {INTERNAL_API_URL}{MANIFEST_SUBMIT_ROUTE}")
           response = await client.post(MANIFEST_SUBMIT_ROUTE, json=payload)
           response.raise_for_status()
           response_json = response.json()
           return f"Internal relay successful, status: {response_json.get('status', 'OK')}"
   except httpx.HTTPStatusError as e:
       error_detail = e.response.json().get("detail", "Unknown Error")
       return f"Internal relay failed (HTTP {e.response.status_code}): {error_detail}"
   except httpx.RequestError as e:
       return f"Critical internal connection error: {e.__class__.__name__}"


def verify_signature(payload: dict, signature: str) -> bool:
   """Verify HMAC SHA-256 signature of the incoming payload."""
   if not HOS_BRIDGE_KEY:
       raise RuntimeError("HOS_BRIDGE_KEY not set in environment. Harmonic Bridge is disabled.")
   message = json.dumps(payload, sort_keys=True).encode("utf-8")
   expected = hmac.new(HOS_BRIDGE_KEY.encode(), message, hashlib.sha256).hexdigest()
   return hmac.compare_digest(expected, signature)


@router.post("/bridge/gemini")
async def bridge_from_gemini(request: Request, x_hos_signature: str = Header(default="")):
   """Accept a signed Gemini payload, verify it, log it, and relay it internally."""
   if not HOS_BRIDGE_KEY:
       raise HTTPException(status_code=503, detail="Harmonic Bridge is misconfigured (HOS_BRIDGE_KEY is missing).")
   try:
       payload = await request.json()
   except json.JSONDecodeError:
       raise HTTPException(status_code=400, detail="Invalid JSON payload.")

   timestamp = datetime.utcnow().isoformat()
   if not verify_signature(payload, x_hos_signature):
       raise HTTPException(status_code=403, detail="Invalid or missing signature. Access denied.")

   with open("bridge_log.jsonl", "a") as log:
       log.write(json.dumps({"timestamp": timestamp, "payload": payload}) + "\n")

   internal_status = await submit_internal_manifest(payload)
   return {
       "status": "ACK",
       "timestamp": timestamp,
       "internal_relay_status": internal_status
   }
