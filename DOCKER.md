# EasyRead Docker Setup

This document describes the Docker workflows that currently exist in this repository.

## Architecture Overview

The containerized EasyRead application consists of:

- **PostgreSQL + pgvector** for vector similarity search
- **Django backend** for the API and processing pipeline
- **React + Vite frontend** for the web UI
- **Nginx** for production/evaluation serving and proxying
- **Redis** as an optional production cache

## Development with Docker Compose

### Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose v2+
- Enough local disk space for Postgres data, media, and frontend build artifacts
- A root `.env` file copied from `.env.example`

### 1. Configure `.env`

```bash
cp .env.example .env
```

For Docker development, the most important values are:

```bash
SECRET_KEY=replace-me
OPENAI_API_KEY=
COHERE_API_KEY=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION_NAME=us-east-1
BACKEND_PORT=8001
```

### 2. Start the development stack

```bash
docker compose up --build -d
```

`docker-compose.override.yml` is applied automatically in development.

### 3. Access the services

With the default compose configuration:

- Frontend: `http://127.0.0.1:5173/`
- Backend API: `http://127.0.0.1:8001/api/health/`
- Postgres: internal to Docker by default

## Common Development Commands

```bash
# Start or rebuild everything
docker compose up --build -d

# Follow backend logs
docker compose logs -f backend

# Run Django migrations
docker compose exec backend python manage.py migrate

# Validate embedding credentials
docker compose exec backend python manage.py validate_api_keys --test-embedding

# Open a Django shell
docker compose exec backend python manage.py shell

# Open a Postgres shell inside the container
docker compose exec postgres psql -U easyread_user -d easyread

# Stop the stack
docker compose down
```

## AWS / EC2 Evaluation Deployment Example

The evaluation compose file builds the frontend into the Nginx image and serves the application behind Nginx. In this repository, it should be treated as an AWS / EC2 evaluation example rather than a complete production playbook.

### Why this is framed as an evaluation example

- It assumes a reverse-proxied HTTPS deployment on a single host such as EC2.
- It defaults to serving the frontend from `/easyread/`, which may not match every environment.
- It expects mounted certificates and a Basic Auth file for evaluator access.
- It is useful for short-lived stakeholder testing, but it is not a full production hardening recipe.

### 1. Create `.env.prod` for the evaluation host

At minimum, set:

```bash
SECRET_KEY=replace-with-a-secure-value
DEBUG=False
ALLOWED_HOSTS=your-hostname
CORS_ALLOWED_ORIGINS=https://your-hostname
DB_NAME=easyread
DB_USER=easyread_user
DB_PASSWORD=replace-me
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION_NAME=us-east-1
VITE_API_BASE_URL=/api
VITE_MEDIA_BASE_URL=
VITE_BASE_URL=/easyread/
VITE_BASE_URL_PROD=/easyread/
```

Notes:

- `VITE_BASE_URL` and `VITE_BASE_URL_PROD` must match the subpath where the app is served.
- If you serve the app from `/easyread/`, the frontend assets will be requested from `/easyread/assets/...`.
- `STATIC_ROOT` is collected inside the backend image and served by Nginx from `/static/`.

### 2. Start the evaluation stack

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d
```

### 3. HTTPS and tester access control used by this example

The current Nginx setup expects TLS certificates mounted from `nginx/ssl/` and uses HTTP Basic Auth via `nginx/.htpasswd` for temporary tester access.

Do **not** commit either of these to the repository. If you do not want TLS + Basic Auth, adjust `docker-compose.prod.yml` and `nginx/default.conf` before using this stack.

If you add HTTP Basic Auth in front of the site, make sure the proxy does not forward that `Authorization` header to Django for API routes, or the backend may interpret the tester credentials as API credentials.

## Troubleshooting

### Frontend assets 404 under `/easyread/assets/`

If the deployed HTML references `/easyread/assets/...`, Nginx must explicitly serve that path. The evaluation config in `nginx/default.conf` includes a dedicated `location ^~ /easyread/assets/` block for this.

### `Failed to load image sets` behind Basic Auth

If `/api/image-sets/` returns `403 Invalid username/password`, your proxy is likely forwarding the tester Basic Auth header to Django. Strip `Authorization` before proxying `/api/` requests.

### `type "vector" does not exist`

The Postgres database exists, but `pgvector` was not enabled in that database. Connect to the database and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Image imports fail even though files exist

Image imports generate embeddings immediately. Validate the configured embedding provider first:

```bash
docker compose exec backend python manage.py validate_api_keys --test-embedding
```

### Long Bedrock-backed requests fail

Tune these environment variables in `.env` or `.env.prod`:

- `AWS_BEDROCK_CONNECT_TIMEOUT`
- `AWS_BEDROCK_READ_TIMEOUT`
- `AWS_BEDROCK_MAX_ATTEMPTS`

## Additional Resources

- `README.md` for the local Python setup
- `API_DOCUMENTATION.md` for backend endpoints
- `SECURITY.md` for security reporting
