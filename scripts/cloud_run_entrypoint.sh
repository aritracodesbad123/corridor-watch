#!/bin/sh
# Cloud Run / container entrypoint.
# GCP must use Cloud SQL PostgreSQL. SQLite is local-only.
# Seeds an empty Cloud SQL database, then starts uvicorn.
set -e
cd /app
if [ "${ENVIRONMENT:-}" = "gcp" ]; then
  case "${DATABASE_URL:-}" in
    postgres://*|postgresql://*) ;;
    *)
      echo "GCP requires DATABASE_URL PostgreSQL; SQLite is local-only" >&2
      exit 1
      ;;
  esac
fi
python - <<'PY'
from pathlib import Path

from config import get_settings
from db import connect, init_schema
from patterns.repository import seed_library
from synthetic.showcase import seed_showcase
from synthetic.middle_bank import seed_middle_bank
from synthetic.world import seed_banks

init_schema()
settings = get_settings()
con = connect()
row = con.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()
con.close()
count = int(row["c"] if row else 0)
if count < 1:
    if settings.is_postgres:
        print("empty Cloud SQL database — seeding ledger")
    else:
        print("fraud_demo.db empty — seeding ledger")
    import data_gen
    from graph_features import score_all, write_scores
    from db import connect as db_connect

    accounts, txns = data_gen.build()
    data_gen.write_db(accounts, txns)
    con = db_connect()
    scores, _, _ = score_all(con)
    write_scores(con, scores, txns)
    con.close()
seed_banks()
seed_library()
seeded = seed_showcase()
middle = seed_middle_bank()
print(f"showcase={seeded['campaign_id']} hero={seeded['hero_txn_id']} middle={middle['hero_txn_id']}")
PY
PORT="${PORT:-8080}"
exec uvicorn main:app --host 0.0.0.0 --port "$PORT"
