from validation.deepeval.metrics.unsupported_claims import unsupported_claims


def test_unsupported_claim_rate_gate():
    allowed = {"E-TXN", "E-NET"}
    rate = unsupported_claims(["E-TXN", "E-FAKE"], allowed)
    assert rate <= 0.5
    assert unsupported_claims(["E-TXN"], allowed) <= 0.05
