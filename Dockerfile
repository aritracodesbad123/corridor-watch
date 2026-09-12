FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x scripts/cloud_run_entrypoint.sh
ENV PORT=8080
CMD ["./scripts/cloud_run_entrypoint.sh"]
