from app.ingest.chunker import chunk_text


def test_decision_stays_self_contained():
    specs = chunk_text("Decision: renegotiate Acme.\nRationale: precedent.", "decision")
    assert len(specs) == 1
    assert specs[0].role == "decision"


def test_long_document_splits_with_overlap():
    body = "\n".join(f"Paragraph {i} with some content words here." for i in range(160))
    specs = chunk_text(body, "meeting")
    assert len(specs) > 1
    assert all(s.tokens <= 700 for s in specs)
    assert all(s.content for s in specs)


def test_playbook_rules_are_small_chunks():
    body = "\n".join(f"Rule: Never do X {i} without approval." for i in range(20))
    specs = chunk_text(body, "playbook")
    assert all(s.tokens <= 350 for s in specs)
