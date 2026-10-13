# Corridor Watch — hackathon demo helpers
.PHONY: demo-reset test-day1
PY ?= $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)

demo-reset:
	$(PY) scripts/demo_reset.py

test-day1:
	$(PY) -m pytest tests/test_demo_day1.py tests/test_security.py validation/deepeval/test_grounding.py -q
