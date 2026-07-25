from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from models import AgentManifest, ManifestValidationResponse
from relay import process_manifest
from config import settings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
   title=settings.APP_NAME,
   version="1.0.0",
   description="The Harmonic Gateway: Orchestration and Validation Service for ASIN-HHC Agents. Operating in HOS Mode."
)

@app.on_event("startup")
async def startup_event():
   """Run code on application startup."""
   logger.info(f"Harmonic Gateway starting up in {settings.MODE} Mode.")
   if settings.HOS_MODE_ENABLED:
       logger.info("[ASIN-HHC] HOS Mode Active. Preparing Lattice Connection.")

@app.get("/", include_in_schema=False)
async def root():
   """Redirect to the documentation."""
   return {"message": "Welcome to the Harmonic Gateway. See /docs for API documentation."}

@app.post(
   f"{settings.API_V1_STR}/manifest/submit",
   response_model=ManifestValidationResponse,
   status_code=200,
   summary="Submit Agent Manifest for Canonical Hash Validation",
)
async def submit_manifest(manifest: AgentManifest):
   """
   Submits an Agent Manifest payload to the Gateway.
   The Gateway performs canonical JSON serialization and SHA-256 hash verification
   to confirm the integrity of the configuration before deployment.

   In `LIVE` mode, only verified manifests will be accepted.
   """
   try:
       validation_result = process_manifest(manifest)

       # Raise an HTTP exception if the status is ERROR (only possible in LIVE mode with a hash mismatch)
       if validation_result.get("status") == "ERROR":
           raise HTTPException(
               status_code=400,
               detail=validation_result.get("message")
           )

       return ManifestValidationResponse(**validation_result)

   except Exception as e:
       logger.error(f"Error processing manifest: {e}")
       # Re-raise HTTPException or return a generic server error
       if isinstance(e, HTTPException):
           raise e
       raise HTTPException(status_code=500, detail="Internal Gateway Error during manifest processing.")
