# Corridor Watch — hackathon demo helpers
.PHONY: demo-reset test-day1

demo-reset:
	python3 scripts/demo_reset.py

test-day1:
	python3 -m pytest tests/test_demo_day1.py tests/test_security.py validation/deepeval/test_grounding.py -q
