# Cloud Run deploy

Cloud Run service with Pub/Sub push ingest, Vertex Gemini, and Cloud SQL PostgreSQL.

```bash
./scripts/setup_cloud_sql.sh YOUR_PROJECT_ID asia-southeast1
./scripts/scale_cloud_sql.sh YOUR_PROJECT_ID
./scripts/deploy_cloud_run.sh YOUR_PROJECT_ID asia-southeast1
```

`DATABASE_URL` is stored in Secret Manager and mounted at runtime. The entrypoint seeds an empty database, then starts uvicorn.

Default Cloud SQL is 2 vCPU / 7.5 GiB (`scripts/scale_cloud_sql.sh`). That is the ingest ceiling, not Cloud Run.
Default Cloud Run deploy is `--cpu 2 --memory 2Gi --min-instances 2 --max-instances 10 --concurrency 16`.
Each replica uses `CW_PG_POOL_MAX=8`, `CW_INGEST_SLOTS=8`. Ten replicas stay under ~200 SQL connections.

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
