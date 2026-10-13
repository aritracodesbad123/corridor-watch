# Corridor Watch — hackathon demo helpers
.PHONY: demo-reset test-day1 shake-check demo-capture
PY ?= $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)
VID ?= film/out/corridor-watch-1080p.mp4

demo-reset:
	$(PY) scripts/demo_reset.py

test-day1:
	$(PY) -m pytest tests/test_demo_day1.py tests/test_security.py validation/deepeval/test_grounding.py -q

# Day-2: fail render if any hold segment shifts >0.3px (phaseCorrelate).
shake-check:
	$(PY) scripts/shake_check.py $(VID)

# Capture real-app plates (server must be up with CW_DEMO_REPLAY=1).
# Prefer Playwright when installed: cd film && npm i -D playwright && npx playwright install chromium
demo-capture:
	cd film && (test -d node_modules/playwright && node scripts/capture-playwright.mjs || node scripts/capture.mjs)
