# Environment Variables Reference

## Required Variables

These variables must be set for the application to function properly.

| Variable | Description | Example | Validation |
|----------|-------------|---------|------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` | Must be valid URL |
| `REDIS_URL` | Redis connection for caching and queues | `redis://host:6379/0` | Must be valid URL |
| `JWT_SECRET` | Secret key for JWT token signing | `a-random-string-min-32-chars` | Min 32 characters |
| `GROQ_API_KEY` | API key for Groq LLM service | `gsk_xxxxx` | Starts with `gsk_` |

## Optional Variables

| Variable | Default | Description | Constraints |
|----------|---------|-------------|-------------|
| `APP_NAME` | `CloudSync` | Application name for logs | Max 50 chars |
| `DEBUG` | `false` | Enable debug mode | `true` or `false` |
| `LOG_LEVEL` | `INFO` | Logging verbosity | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ENVIRONMENT` | `production` | Deployment environment | `development`, `staging`, `production` |
| `API_HOST` | `0.0.0.0` | API bind address | Valid IP address |
| `API_PORT` | `8000` | API port | 1024-65535 |
| `AWS_REGION` | `us-east-1` | AWS region code | Valid AWS region |
| `S3_BUCKET` | - | S3 bucket for file storage | Valid bucket name |
| `MAX_UPLOAD_SIZE` | `104857600` | Max file upload (bytes) | Max 1GB (1073741824) |
| `RATE_LIMIT_PER_MIN` | `100` | API rate limit per user | 1-10000 |
| `VECTOR_STORE_PATH` | `./data/chroma_db` | Chroma DB storage path | Valid directory path |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace model name | Valid model identifier |

## Development-Specific Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `RELOAD` | Enable auto-reload on code changes | `true` |
| `WORKERS` | Number of Uvicorn workers | `1` (dev) / `4` (prod) |

## Security Variables

| Variable | Description | Notes |
|----------|-------------|-------|
| `ALLOWED_HOSTS` | Comma-separated allowed domains | `api.cloudsync.com,localhost` |
| `CORS_ORIGINS` | Allowed CORS origins | `https://app.cloudsync.com` |
| `SECURE_SSL_REDIRECT` | Force HTTPS | `true` in production |

## Agent Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PLANNER_MODEL` | `llama-3.1-70b-versatile` | Groq model for query planning |
| `VALIDATOR_MODEL` | `llama-3.1-70b-versatile` | Groq model for validation |
| `SYNTHESIZER_MODEL` | `llama-3.1-70b-versatile` | Groq model for response generation |
| `PLANNER_TEMPERATURE` | `0.1` | Temperature for planning (low = focused) |
| `VALIDATOR_TEMPERATURE` | `0.0` | Temperature for validation (deterministic) |
| `SYNTHESIZER_TEMPERATURE` | `0.3` | Temperature for synthesis (balanced) |
| `MAX_RETRIEVAL_CHUNKS` | `10` | Maximum chunks to retrieve per query |
| `VALIDATION_THRESHOLD` | `0.6` | Minimum confidence for valid chunks |
| `CHUNK_SIZE` | `500` | Document chunk size in tokens |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks in tokens |

## Performance Tuning

| Variable | Default | Description | When to Increase |
|----------|---------|-------------|------------------|
| `DB_POOL_SIZE` | `10` | PostgreSQL connection pool | High concurrent load |
| `DB_MAX_OVERFLOW` | `20` | Extra connections when busy | Traffic spikes |
| `REDIS_POOL_SIZE` | `50` | Redis connection pool | Many workers |
| `CELERY_WORKERS` | `4` | Celery concurrent workers | CPU-intensive tasks |
| `REQUEST_TIMEOUT` | `30` | HTTP request timeout (seconds) | Slow LLM responses |

## Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_STREAMING` | `true` | Stream LLM responses |
| `ENABLE_RETRIEVAL_FALLBACK` | `true` | Retry retrieval if validation fails |
| `ENABLE_QUERY_CACHE` | `false` | Cache frequent queries (Redis) |
| `ENABLE_SOURCE_ATTRIBUTION` | `true` | Include sources in responses |

## Example Configuration Files

### Development (.env.development)
```env
DEBUG=true
LOG_LEVEL=DEBUG
ENVIRONMENT=development

DATABASE_URL=postgresql://cloudsync:cloudsync@localhost:5432/cloudsync_dev
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=dev-secret-key-not-for-production
GROQ_API_KEY=gsk_your_development_key

VECTOR_STORE_PATH=./data/chroma_db
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

PLANNER_MODEL=llama-3.1-8b-instant
VALIDATOR_MODEL=llama-3.1-8b-instant
SYNTHESIZER_MODEL=llama-3.1-8b-instant

ENABLE_STREAMING=true
RELOAD=true
WORKERS=1
```

### Production (.env.production)
```env
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=production

DATABASE_URL=postgresql://prod_user:xxx@prod-db.cluster-xxx.us-east-1.rds.amazonaws.com:5432/cloudsync
REDIS_URL=rediss://master.xxx.cache.amazonaws.com:6379/0
JWT_SECRET=<generate-strong-secret>
GROQ_API_KEY=gsk_your_production_key

AWS_REGION=us-east-1
S3_BUCKET=cloudsync-prod-files

VECTOR_STORE_PATH=/app/data/chroma_db
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

PLANNER_MODEL=llama-3.1-70b-versatile
VALIDATOR_MODEL=llama-3.1-70b-versatile
SYNTHESIZER_MODEL=llama-3.1-70b-versatile

PLANNER_TEMPERATURE=0.1
VALIDATOR_TEMPERATURE=0.0
SYNTHESIZER_TEMPERATURE=0.3

CHUNK_SIZE=500
CHUNK_OVERLAP=50
MAX_RETRIEVAL_CHUNKS=10
VALIDATION_THRESHOLD=0.6

DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
REDIS_POOL_SIZE=100

ENABLE_STREAMING=true
ENABLE_RETRIEVAL_FALLBACK=true
ENABLE_QUERY_CACHE=true
ENABLE_SOURCE_ATTRIBUTION=true

ALLOWED_HOSTS=api.cloudsync.com
CORS_ORIGINS=https://app.cloudsync.com
SECURE_SSL_REDIRECT=true

WORKERS=4
```

## Validation

The application validates environment variables on startup:

1. **Required vars**: Missing → Startup fails with error
2. **Format validation**: Invalid URL/port/format → Startup fails
3. **Security checks**: Weak JWT secret → Warning logged
4. **Model availability**: Groq API key tested → Warning if invalid

## Secrets Management

**Never commit secrets to git!**

### Local Development
Use `.env` file (already in `.gitignore`)

### Production

**AWS Secrets Manager:**
```bash
# Store secret
aws secretsmanager create-secret \
  --name cloudsync/production/database-url \
  --secret-string "postgresql://..."

# Reference in ECS task definition
"secrets": [
  {
    "name": "DATABASE_URL",
    "valueFrom": "arn:aws:secretsmanager:...:secret:cloudsync/production/database-url"
  }
]
```

**Docker Secrets (Swarm mode):**
```bash
echo "postgresql://..." | docker secret create db_url -
docker service create --secret db_url cloudsync-api
```

**Kubernetes Secrets:**
```bash
kubectl create secret generic cloudsync-secrets \
  --from-literal=database-url='postgresql://...' \
  --from-literal=jwt-secret='xxx'
```

## Troubleshooting

### "Missing required environment variable"
Check that all required vars from the table above are set.

### "Invalid DATABASE_URL format"
Must follow pattern: `postgresql://user:password@host:port/database`

### "Groq API key invalid"
- Verify key starts with `gsk_`
- Test with: `curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"`

### "JWT secret too short"
Must be at least 32 characters. Generate with: `openssl rand -hex 32`