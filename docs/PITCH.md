# Corridor Watch — pitch notes (3-minute + client)

## One-liner

Graph fraud detection is commoditized. Corridor Watch is the **agentic investigation
and institutional-memory layer** that turns alerts into audit-ready analyst judgments.

## Problem (30s)

JAPAC remittance corridors hide mule networks, synthetic IDs, and split laundering
that no single transaction reveals. Analysts drown in false positives, and even when
ML scores fire, someone still has to translate a number into a regulator-ready story.

## Why not "just buy Actimize / Feedzai / Quantexa"?

Those platforms already do graph correlation, SAR narrative assist, and adverse media.
**Do not lead with detection.** Lead with what they don't package as a vertical product:

1. **Source-of-funds plausibility** — inconsistency list, not a score
2. **Institutional case memory** — "what did we do last time on a case like this?"
3. **MRM draft automation** — first-pass validation docs with red-team gaps as limitations
4. **Continuous adversarial self-testing** — novel patterns run through *your* pipeline

## Demo flow (3 min)

1. Open queue — sort by risk; pick a high mule pass-through alert  
2. Overview + behavioral biometrics + network neighborhood  
3. **Run investigation** — show 12-step DAG trace + evidence-grounded verdict  
4. Phase 2: SoF check inconsistencies + precedent retrieval  
5. Record analyst decision (writes to case memory)  
6. Optional: MRM draft / red-team evasion report  

## Objection: "We won't send bank data to Google/OpenAI"

Agree. Architecture is **thin + swappable**:

- POC: synthetic data only  
- Production: Azure OpenAI in **client tenant**, private endpoints, CMK, zero-retention contract  
- Every AI call audited  
- Deterministic DAG works with the LLM off  

## Ask

Pilot on synthetic → shadow mode on historical alerts (no payment actions) →
measure analyst handle time + override rate → expand to SoF + MRM workflows.
