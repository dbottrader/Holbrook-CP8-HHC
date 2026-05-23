from fastapi import FastAPI
import hashlib, time

app = FastAPI(title="ASIN-HHC HOS Integrity API")

def hash_payload(p):
    return hashlib.sha256(str(p).encode()).hexdigest()

@app.get("/audit")
def audit():
    payload = {
        "id": "audit_demo",
        "timestamp": time.time(),
        "rooms": ["Vault","Resonance","Workshop","Bridge"],
        "glyphs": ["❖","𓂀","◎","✶"],
        "status": "PASS"
    }
    payload["checksum"] = hash_payload(payload)
    return payload

@app.get("/neuromap")
def neuromap():
    return {
        "version": "demo_0.1",
        "nodes": ["anchor","weave","flux","mirror","memory","intent","bridge"]
    }

@app.get("/sync")
def sync():
    return {
        "agents": ["ace_sim","glyph_engine_sim","leystudio_sim"],
        "sync_hash": hash_payload("sync"),
        "state": "coherent"
    }
