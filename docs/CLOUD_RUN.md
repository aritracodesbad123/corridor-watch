# Cloud Run deploy

Cloud Run service with Pub/Sub push ingest, Vertex Gemini, and Cloud SQL PostgreSQL.

```bash
./scripts/setup_cloud_sql.sh YOUR_PROJECT_ID asia-southeast1
./scripts/deploy_cloud_run.sh YOUR_PROJECT_ID asia-southeast1
```

`DATABASE_URL` is stored in Secret Manager and mounted at runtime. The entrypoint seeds an empty database, then starts uvicorn.

`--min-instances 1` keeps a warm instance. Cloud SQL is required before raising `--max-instances`.
