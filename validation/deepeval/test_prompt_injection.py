from pathlib import Path

from privacy import wrap_untrusted

CORPUS = Path(__file__).resolve().parents[1] / "datasets" / "injection_corpus.jsonl"


def test_injected_instructions_are_redacted():
    hijacks = 0
    for line in CORPUS.read_text().splitlines():
        text = __import__("json").loads(line)["text"]
        wrapped = wrap_untrusted(text)
        body = wrapped["content"]
        if "Ignore previous" in body or "You are now" in body or "System prompt:" in body:
            hijacks += 1
    assert hijacks == 0
    assert wrapped["untrusted_data"] is True
