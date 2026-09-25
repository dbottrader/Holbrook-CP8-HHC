from fastapi import FastAPI, HTTPException\nfrom fastapi.responses import FileResponse
from pydantic import BaseModel

from .runtime import HolbrookRuntime
from .storage import ReceiptStore

app = FastAPI(title="Holbrook OS", version="0.2.0")
store = ReceiptStore("data/holbrook_receipts.sqlite3")
runtime = HolbrookRuntime(store=store)


class RunRequest(BaseModel):
    prompt: str


@app.get("/", include_in_schema=False)\ndef dashboard():\n    return FileResponse("holbrook_os/dashboard.html")\n\n\n@app.get("/health")
def health():
    return {"status": "ok", "runtime": "holbrook-os/0.2.0"}


@app.post("/run")
def run(request: RunRequest):
    try:
        return runtime.run(request.prompt).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/receipts")
def receipts(limit: int = 100):
    return {"receipts": store.list(max(1, min(limit, 500)))}


@app.get("/receipts/{receipt_id}")
def receipt(receipt_id: str):
    item = store.get(receipt_id)
    if item is None:
        raise HTTPException(status_code=404, detail="receipt not found")
    return item


@app.get("/verify/{receipt_id}")
def verify(receipt_id: str):
    item = store.get(receipt_id)
    if item is None:
        raise HTTPException(status_code=404, detail="receipt not found")
    return {"receipt_id": receipt_id, "valid": HolbrookRuntime.verify(item)}
