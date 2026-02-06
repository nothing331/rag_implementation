# API Reference

## Base URL

- **Development**: `http://localhost:8000`
- **Staging**: `https://api-staging.cloudsync.com`
- **Production**: `https://api.cloudsync.com`

## Authentication

All endpoints (except health check) require JWT Bearer token:

```
Authorization: Bearer <jwt_token>
```

Obtain token via OAuth2 login or API key exchange.

## Endpoints

### 1. Query (Main RAG Endpoint)

**POST** `/api/v1/query`

Process a natural language query through the agentic RAG pipeline.

**Request Body:**
```json
{
  "query": "How do I deploy to AWS with Docker?",
  "session_id": "optional-user-session-id",
  "max_sources": 3
}
```

**Parameters:**
- `query` (string, required): The user question
- `session_id` (string, optional): For tracking multi-turn conversations
- `max_sources` (integer, optional, default: 5): Maximum number of source citations

**Response:**
```json
{
  "answer": "To deploy CloudSync to AWS with Docker, follow these steps:\n\n1. Build your Docker image using the multi-stage Dockerfile\n2. Push to Amazon ECR\n3. Create an ECS cluster with Fargate\n4. Configure Application Load Balancer with SSL\n\nMake sure to set the required environment variables including DATABASE_URL and JWT_SECRET.",
  "sources": [
    {
      "document": "deployment/docker-guide.md",
      "section": "Production Dockerfile",
      "relevance_score": 0.94,
      "content_preview": "Multi-stage build for smaller image..."
    },
    {
      "document": "deployment/aws-setup.md",
      "section": "Step-by-Step Deployment",
      "relevance_score": 0.89,
      "content_preview": "1. Build and Push Docker Image..."
    }
  ],
  "metadata": {
    "processing_time_ms": 1250,
    "tokens_used": 450,
    "confidence": 0.92,
    "sub_queries": [
      "Find AWS deployment steps",
      "Find Docker configuration for production"
    ],
    "model_used": "llama-3.1-70b-versatile"
  }
}
```

**Response Fields:**
- `answer` (string): Generated response with inline citations [1], [2]
- `sources` (array): List of source documents
  - `document` (string): Document path/name
  - `section` (string): Section title
  - `relevance_score` (float): 0.0-1.0 relevance score
  - `content_preview` (string): Brief excerpt
- `metadata` (object): Processing details
  - `processing_time_ms` (integer): Total processing time
  - `tokens_used` (integer): LLM tokens consumed
  - `confidence` (float): Overall answer confidence
  - `sub_queries` (array): Query decomposition steps
  - `model_used` (string): Groq model name

**Status Codes:**
- `200 OK`: Successful query
- `400 Bad Request`: Invalid request format
- `401 Unauthorized`: Missing or invalid token
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Processing error

**Example Usage:**
```bash
curl -X POST https://api.cloudsync.com/api/v1/query \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I deploy to AWS?",
    "max_sources": 3
  }'
```

### 2. Health Check

**GET** `/health`

Check service health and dependencies.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "dependencies": {
    "vector_store": {
      "status": "connected",
      "latency_ms": 5,
      "document_count": 45
    },
    "llm_service": {
      "status": "available",
      "provider": "groq",
      "model": "llama-3.1-70b-versatile"
    }
  }
}
```

**Status Codes:**
- `200 OK`: All systems operational
- `503 Service Unavailable`: One or more dependencies down

**Example Usage:**
```bash
curl https://api.cloudsync.com/health
```

### 3. Document Ingestion

**POST** `/api/v1/ingest`

Trigger re-ingestion of documentation. Admin only.

**Request Body:**
```json
{
  "force": false,
  "paths": ["docs/architecture", "docs/deployment"]
}
```

**Parameters:**
- `force` (boolean, optional, default: false): Re-ingest even if unchanged
- `paths` (array, optional): Specific directories to ingest (default: all)

**Response:**
```json
{
  "status": "success",
  "documents_processed": 7,
  "chunks_created": 45,
  "chunks_updated": 0,
  "chunks_deleted": 0,
  "processing_time_ms": 3200,
  "errors": []
}
```

**Status Codes:**
- `202 Accepted`: Ingestion started (async)
- `400 Bad Request`: Invalid paths or parameters
- `401 Unauthorized`: Missing admin privileges
- `409 Conflict`: Ingestion already in progress

**Example Usage:**
```bash
curl -X POST https://api.cloudsync.com/api/v1/ingest \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "force": true,
    "paths": ["docs/deployment"]
  }'
```

### 4. Query with Streaming

**POST** `/api/v1/query/stream`

Stream the response token-by-token for better UX.

**Request Body:** Same as `/api/v1/query`

**Response:** Server-Sent Events (SSE) stream

**Event Types:**
- `token`: Individual response token
- `sources`: Source citations (sent once when available)
- `metadata`: Processing metadata (sent at end)
- `error`: Error message if processing fails
- `done`: Stream completion marker

**Example Stream:**
```
event: token
data: {"token": "To"}

event: token
data: {"token": " deploy"}

event: sources
data: {"sources": [{"document": "deployment/aws-setup.md", "relevance_score": 0.94}]}

event: metadata
data: {"processing_time_ms": 1250, "tokens_used": 450}

event: done
data: {}
```

**Example Usage:**
```javascript
const eventSource = new EventSource('/api/v1/query/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'How do I deploy?' })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.token) appendToUI(data.token);
  if (data.sources) displaySources(data.sources);
};
```

## Rate Limiting

- **Standard tier**: 100 requests/minute
- **Premium tier**: 1000 requests/minute
- **Burst limit**: 20 requests/second

Rate limit headers included in all responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705315800
```

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The 'query' field is required",
    "details": {
      "field": "query",
      "issue": "missing"
    },
    "request_id": "req_abc123xyz"
  }
}
```

**Error Codes:**
- `INVALID_REQUEST`: Malformed request
- `UNAUTHORIZED`: Authentication required
- `FORBIDDEN`: Insufficient permissions
- `NOT_FOUND`: Resource not found
- `RATE_LIMITED`: Too many requests
- `INTERNAL_ERROR`: Server error

## Versioning

API versions are URL-based:
- Current: `/api/v1/`
- Previous: `/api/v0/` (deprecated, removed in 6 months)

Breaking changes bump the version number.

## SDK Examples

### Python
```python
import requests

headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Content-Type": "application/json"
}

response = requests.post(
    "https://api.cloudsync.com/api/v1/query",
    headers=headers,
    json={"query": "How do I deploy to AWS?"}
)

data = response.json()
print(data["answer"])
```

### JavaScript/TypeScript
```typescript
const queryRAG = async (question: string) => {
  const response = await fetch('https://api.cloudsync.com/api/v1/query', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query: question }),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  return response.json();
};
```

### cURL
```bash
# Simple query
curl -X POST https://api.cloudsync.com/api/v1/query \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I deploy?"}'

# Pretty print response
curl -s -X POST https://api.cloudsync.com/api/v1/query \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I deploy?"}' | jq .
```

## Webhooks (Future)

Planned for v1.1:
- Document updated notification
- Query analytics export
- New document detection

## OpenAPI Specification

Full OpenAPI spec available at:
- JSON: `https://api.cloudsync.com/openapi.json`
- UI: `https://api.cloudsync.com/docs`

Use for client generation and automated testing.