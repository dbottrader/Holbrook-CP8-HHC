from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from hos.harmonic_algebra.core import bounded_correction, evaluate_state
from hos.runtime.asinhhccp8_hos import ASINPacket, HOSReceipt, process_packet, verify_receipt

try:
    from supabase import Client, create_client
except ImportError:
    Client = Any  # type: ignore
    create_client = None

app = FastAPI(
    title="ASIN-HHC-CP8 HOS API",
    version="0.1.0",
    description="Receipt-driven reference runtime for ASIN packets and measurable harmonic-state correction.",
)


class ProcessRequest(BaseModel):
    anchor: str = Field(min_length=1)
    shape: str = Field(min_length=1)
    intention: str = Field(min_length=1)
    number: int = 428
    rooms: list[str] = Field(default_factory=lambda: ["Vault", "Resonance", "Workshop", "Bridge"])
    evidence_tier: str = "E0"
    actions: list[str] = Field(default_factory=list)
    persist: bool = False


class VerifyRequest(BaseModel):
    receipt_id: str
    created_at: str
    packet: dict[str, Any]
    packet_sha256: str
    actions: list[str] = Field(default_factory=list)
    checks: dict[str, Any]
    authority: str = "USER_REVIEW_REQUIRED"
    runtime_claim: str = "REFERENCE_IMPLEMENTATION"


class HarmonicStateRequest(BaseModel):
    ideal: list[float] = Field(min_length=1)
    actual: list[float] = Field(min_length=1)
    namespace: int = 428
    alpha: float = Field(default=1.0, gt=0.0, le=1.0)
    bound: float = Field(default=1.0, gt=0.0)


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
        "harmonic_algebra": "OPERATIONAL_MEASURABLE_STATE_V1",
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
def verify(request: VerifyRequest) -> dict[str, bool]:
    receipt = HOSReceipt(
        receipt_id=request.receipt_id,
        created_at=request.created_at,
        packet=request.packet,
        packet_sha256=request.packet_sha256,
        actions=tuple(request.actions),
        checks=request.checks,
        authority=request.authority,
        runtime_claim=request.runtime_claim,
    )
    return {"valid": verify_receipt(receipt)}


@app.post("/v1/harmonic-state")
def harmonic_state(request: HarmonicStateRequest) -> dict[str, Any]:
    try:
        result = evaluate_state(request.ideal, request.actual, request.namespace)
        next_state = bounded_correction(
            request.ideal,
            request.actual,
            alpha=request.alpha,
            bound=request.bound,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        **result.__dict__,
        "next_state": next_state,
        "formula": "E_HOS = 1 / (1 + ||ideal - actual||_2)",
        "claim_boundary": "engineering metric; namespace labels have no independent physical or cryptographic effect",
    }


@app.get("/v1/manifest")
def manifest() -> dict[str, Any]:
    return {
        "system": "ASIN-HHC-CP8 HOS",
        "release": "0.1.0",
        "objects": ["ASINPacket", "HOSReceipt", "HarmonicStateResult"],
        "storage": ["local", "Supabase optional"],
        "model": "CP8 GPT-2-class E0 architecture; no trained weights",
        "harmonic_algebra": "operational state/correction operators plus canonical SHA-256 receipts",
        "authority": "human review required",
    }
