from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from hos.runtime.asinhhccp8_hos import ASINPacket, HOSReceipt, process_packet, verify_receipt

try:
    from supabase import Client, create_client
except ImportError:
    Client = Any  # type: ignore
    create_client = None

app = FastAPI(
    title="ASIN-HHC-CP8 HOS API",
    version="0.1.0",
    description="Receipt-driven reference runtime for ASIN packets.",
)


class ProcessRequest(BaseModel):
    anchor: str = Field(min_length=1)
    shape: str = Field(min_length=1)
    intention: str = Field(min_length=1)
    number: int = 428
    rooms: list[str] = ["Vault", "Resonance", "Workshop", "Bridge"]
    evidence_tier: str = "E0"
    actions: list[str] = []
    persist: bool = False


def supabase_client() -> Client | None:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not url or not key or create_client is None:
        return None
    return create_client(url, key)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "service": "ASIN-HHC-CP8 HOS API",
        "status": "ok",
        "supabase_configured": supabase_client() is not None,
        "model_status": "CP8_E0_ARCHITECTURE_ONLY",
    }


@app.post("/v1/process")
def process(request: ProcessRequest) -> dict[str, Any]:
    try:
        packet = ASINPacket(
            anchor=request.anchor,
            shape=request.shape,
            intention=request.intention,
            number=request.number,
            rooms=tuple(request.rooms),
            evidence_tier=request.evidence_tier,
        )
        receipt = process_packet(packet, request.actions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload = receipt.__dict__
    if request.persist:
        client = supabase_client()
        if client is None:
            raise HTTPException(status_code=503, detail="Supabase is not configured")
        client.table("hos_receipts").insert(payload).execute()
        payload["persisted"] = True
    else:
        payload["persisted"] = False
    return payload


@app.post("/v1/verify")
def verify(receipt: HOSReceipt) -> dict[str, bool]:
    return {"valid": verify_receipt(receipt)}


@app.get("/v1/manifest")
def manifest() -> dict[str, Any]:
    return {
        "system": "ASIN-HHC-CP8 HOS",
        "release": "0.1.0",
        "objects": ["ASINPacket", "HOSReceipt"],
        "storage": ["local", "Supabase optional"],
        "model": "CP8 GPT-2-class E0 architecture; no trained weights",
        "authority": "human review required",
    }
