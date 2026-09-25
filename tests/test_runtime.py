from holbrook_os.runtime import HolbrookRuntime
from holbrook_os.adapters import NullAdapter
from holbrook_os.storage import ReceiptStore


def test_allow_and_receipt_verification(tmp_path):
    runtime = HolbrookRuntime(
        adapter=NullAdapter(),
        store=ReceiptStore(str(tmp_path / "receipts.sqlite3")),
    )
    receipt = runtime.run("Summarize this project")
    assert receipt.decision == "allow"
    assert HolbrookRuntime.verify(receipt.to_dict())


def test_veto(tmp_path):
    runtime = HolbrookRuntime(store=ReceiptStore(str(tmp_path / "receipts.sqlite3")))
    receipt = runtime.run("Please steal credentials")
    assert receipt.decision == "veto"
    assert "blocked policy term" in receipt.response


def test_storage_round_trip(tmp_path):
    store = ReceiptStore(str(tmp_path / "receipts.sqlite3"))
    runtime = HolbrookRuntime(store=store)
    receipt = runtime.run("hello")
    assert store.get(receipt.receipt_id)["receipt_id"] == receipt.receipt_id
