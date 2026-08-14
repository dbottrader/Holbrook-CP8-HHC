from envelope import text_envelope
from receipt import CP8Receipt


def test_text_envelope_round_trip():
    env = text_envelope(
        "Ace back to base",
        model_id="holbrook-local-model",
        metadata={"room": "Bridge"},
    )
    assert env.verify_integrity()
    assert env.capability_allowed()
    packet = env.runtime_packet()
    assert packet["input"]["text"] == "Ace back to base"
    assert packet["metadata"]["cp8"]["seal"] == env.seal


def test_scope_gate_blocks_ungranted_capability():
    env = text_envelope(
        "test",
        capability="tool.write",
        scopes=["model.run"],
    )
    assert env.verify_integrity()
    assert not env.capability_allowed()
    assert not env.valid()


def test_receipt_links_output_to_envelope():
    env = text_envelope("test", model_id="local-model")
    output = {"text": "ok"}
    receipt = CP8Receipt.from_output(
        env.envelope_id,
        output,
        model_id=env.model_id,
    ).sealed()
    assert receipt["envelope_id"] == env.envelope_id
    assert len(receipt["output_hash"]) == 64
    assert len(receipt["receipt_hash"]) == 64
