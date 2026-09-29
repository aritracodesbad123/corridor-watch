# Cloud Run deploy

Cloud Run service with Pub/Sub push ingest, Vertex Gemini, and Cloud SQL PostgreSQL.

```bash
./scripts/setup_cloud_sql.sh YOUR_PROJECT_ID asia-southeast1
./scripts/scale_cloud_sql.sh YOUR_PROJECT_ID
./scripts/deploy_cloud_run.sh YOUR_PROJECT_ID asia-southeast1
```

`DATABASE_URL` is stored in Secret Manager and mounted at runtime. The entrypoint seeds an empty database, then starts uvicorn.

The default deploy keeps cost down: Cloud SQL `db-f1-micro` (`scripts/scale_cloud_sql.sh`) and Cloud Run `--cpu 1 --memory 1Gi --min-instances 0 --max-instances 1 --concurrency 80`, with CPU charged only while a request is in flight. The pool defaults are `CW_PG_POOL_MAX=2` and `CW_INGEST_SLOTS=2`.
The README’s 814 TPS result was measured on a larger shape (`db-custom-2-7680`, Cloud Run max 10). That shape is an override (`CW_SQL_TIER`, `CW_CPU`, `CW_MIN_INSTANCES`, `CW_MAX_INSTANCES`), not what `./scripts/deploy_cloud_run.sh` does now. The table below is an earlier, lower-rate run on that larger SQL tier.

Override with `CW_CPU`, `CW_MEMORY`, `CW_MIN_INSTANCES`, `CW_MAX_INSTANCES`, `CW_CONCURRENCY`.

Measure the live path with:

```bash
python pubsub_load_generator.py --pubsub --pretty --persist \
  --project YOUR_PROJECT --rate 1000 --duration 20 \
  --command-url https://YOUR_SERVICE --token FIU_BEARER
```

Report `achieved_tps` from that run. Do not treat `--in-process` or HTTP batch numbers as Pub/Sub scale proof.

Measured Pub/Sub → Cloud Run → Cloud SQL (2026-09-13), after raising SQL to `db-custom-2-7680` and Cloud Run to max 10:

| SQL tier | Target | Published | Publish TPS | Ledger processed | Achieved TPS | P50 |
|---|---:|---:|---:|---:|---:|---:|
| db-f1-micro | 300 | 4,500 | 299.92 | 502 | 1.55 | 8.1s |
| db-custom-2-7680 | 200 | 4,000 | 199.95 | 2,402 | 5.65 | 118ms |

The publisher holds the target. Consume is still SQL/connector-bound (503s when the pool is cold or saturated). Do not claim 5,000 TPS.

Do not raise Cloud Run max instances, concurrency, and pool size together. Measure the matrix in [COMPETITION_CLAIMS.md](COMPETITION_CLAIMS.md) first. Timestamped generator output lands in `benchmarks/results/` (no secrets).

The entrypoint exits if `ENVIRONMENT=gcp` and `DATABASE_URL` is not PostgreSQL.

Backups: `./scripts/enable_sql_pitr.sh YOUR_PROJECT_ID` then `./scripts/dr_status.sh YOUR_PROJECT_ID`. Do not claim RPO/RTO until a restore is timed.

Optional SSO: set `OIDC_ISSUER`, `OIDC_AUDIENCE`, and either Google Identity (`https://accounts.google.com`) or `OIDC_CLIENT_SECRET` for an HS256 IdP. Map emails with `OIDC_EMAIL_ROLES`. High-risk actions then require an MFA claim. Password login stays for the competition console.

`CW_PII_HMAC_KEY` should live in Secret Manager (`pii-hmac-key`). It tokenizes account IDs before they reach Gemini. It is not a Cloud KMS client.
