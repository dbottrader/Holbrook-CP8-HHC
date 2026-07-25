from hos.harmonic_algebra.core import bounded_correction, harmonic_state
from hos.runtime.asinhhccp8_hos import ASINPacket, process_packet, verify_receipt


def main() -> None:
    packet = ASINPacket(
        anchor="local verification",
        shape="receipt test",
        intention="prove deterministic packet integrity",
        number=428,
    )
    receipt = process_packet(packet, ["canonicalize", "hash", "review"])
    assert verify_receipt(receipt)
    assert harmonic_state([1.0, 1.0], [1.0, 1.0]) == 1.0
    corrected = bounded_correction([1.0, 1.0], [0.0, 2.0], alpha=0.5, bound=1.0)
    assert corrected == (0.5, 1.5)
    print("PASS", receipt.receipt_id, receipt.packet_sha256)


if __name__ == "__main__":
    main()
