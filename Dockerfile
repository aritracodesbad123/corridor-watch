FROM node:22-bookworm-slim AS webbuild
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# React console is the product UI at /.
COPY --from=webbuild /web/dist ./web/dist
RUN chmod +x scripts/cloud_run_entrypoint.sh
ENV PORT=8080
CMD ["./scripts/cloud_run_entrypoint.sh"]
