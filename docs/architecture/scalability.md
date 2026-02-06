# Scalability Guide

## Overview
CloudSync is designed to scale from hundreds to millions of users. This document covers scaling strategies for each component.

## Current Architecture Limits

| Component | Single Instance Limit | Scaling Strategy |
|-----------|----------------------|------------------|
| API Gateway | 10,000 RPS | Kong clustering |
| WebSocket Server | 10,000 connections | Horizontal scaling |
| Celery Workers | 1000 jobs/sec | Auto-scaling ECS |
| PostgreSQL | 50,000 TPS | Read replicas + sharding |
| Redis | 100,000 ops/sec | Cluster mode |
| S3 | Unlimited | N/A (serverless) |

## Scaling Strategies by Component

### 1. API Gateway (Kong)

**Single Node Limits:**
- 10,000 requests per second
- 100 concurrent WebSocket upgrades/sec

**Horizontal Scaling:**
```yaml
# docker-compose for Kong cluster
services:
  kong:
    image: kong:3.5
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: kong-db
      KONG_PLUGINS: rate-limiting,prometheus
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
```

**Database Configuration:**
- Use separate PostgreSQL instance for Kong (not shared with app)
- Enable connection pooling (PgBouncer)
- Read replicas for config reads

### 2. WebSocket Layer

**Load Balancing Strategy:**
- Use Application Load Balancer (ALB) with sticky sessions
- Hash-based routing: `user_id % server_count`
- WebSocket connections pinned to specific backend

**Scaling Triggers:**
- Scale up: > 8,000 connections per server
- Scale down: < 4,000 connections per server
- Cooldown: 5 minutes between scaling events

**Auto-scaling Configuration:**
```bash
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name websocket-servers \
  --policy-name connection-target-tracking \
  --target-tracking-configuration file://config.json

# config.json
{
  "TargetValue": 8000.0,
  "PredefinedMetricSpecification": {
    "PredefinedMetricType": "ASGAverageConnections"
  }
}
```

### 3. Application Services (FastAPI)

**Container Resources:**
- CPU: 0.5 vCPU (configurable)
- Memory: 1GB (configurable)
- Max concurrent requests: 100 per container

**ECS Service Auto-scaling:**
```json
{
  "TargetValue": 70.0,
  "ScaleUpCooldown": 60,
  "ScaleDownCooldown": 300,
  "MetricType": "ECSServiceAverageCPUUtilization"
}
```

**Request Queuing:**
- Use ALB connection draining (30 seconds)
- Implement circuit breakers (resilience4j)
- Queue depth monitoring for backpressure

### 4. Database (PostgreSQL)

**Read Scaling:**
- Add read replicas for analytics and reporting
- Route read-only queries to replicas
- Maximum 5 read replicas per region

**Write Scaling:**
- Vertical scaling first: db.r5.2xlarge → db.r5.4xlarge
- Connection pooling: PgBouncer (max 1000 connections)
- Partitioning: Tenant-based for multi-tenant isolation

**Query Optimization:**
- Add indexes on: user_id, created_at, updated_at
- Partition large tables by date (monthly)
- Archive data older than 1 year to S3

**Caching Strategy:**
```python
# Redis cache layer
@cache(ttl=300)  # 5 minutes
def get_user_config(user_id: str):
    return db.query(UserConfig).filter_by(user_id=user_id).first()
```

### 5. Redis (ElastiCache)

**Cluster Mode:**
- Enable cluster mode for horizontal scaling
- 3 shards × 2 replicas = 6 nodes total
- Max memory: 500GB across cluster

**Eviction Policy:**
- `allkeys-lru` for general cache
- `noeviction` for job queues (monitor memory!)

**Connection Limits:**
- 65,000 connections per node
- Use connection pooling (redis-py with connection pool)
- Enable TLS for all connections

### 6. Celery Workers

**Queue Architecture:**
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Priority   │────▶│  Real-time   │────▶│  10 workers │
│  Queue      │     │  Workers     │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Default    │────▶│  Standard    │────▶│  20 workers │
│  Queue      │     │  Workers     │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Batch      │────▶│  Heavy       │────▶│  5 workers  │
│  Queue      │     │  Workers     │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
```

**Worker Configuration:**
- Prefetch multiplier: 4 (tasks per worker)
- Task time limit: 300 seconds
- Max memory per worker: 512MB
- Auto-restart after 1000 tasks (memory leak prevention)

## Performance Benchmarks

### Load Testing Results

| Users | Connections | RPS | Latency (p95) | Infrastructure |
|-------|-------------|-----|---------------|--------------|
| 100 | 100 | 50 | 45ms | 1x ECS task |
| 1,000 | 1,000 | 500 | 52ms | 2x ECS tasks |
| 10,000 | 10,000 | 5,000 | 78ms | 4x ECS tasks, 2x WebSocket |
| 100,000 | 100,000 | 50,000 | 120ms | 10x ECS, 10x WebSocket, 2x RDS read |

### Bottleneck Analysis

**First bottleneck**: Database write capacity
- Solution: Vertical scaling + partitioning

**Second bottleneck**: WebSocket connection limits
- Solution: Horizontal scaling with smart routing

**Third bottleneck**: Redis memory
- Solution: Cluster mode + data eviction policies

## Cost Optimization

### Reserved Instances
- Purchase 1-year reserved capacity for baseline load
- Use spot instances for Celery workers (30% cheaper)

### Right-sizing
- Monitor actual usage vs provisioned
- Use AWS Compute Optimizer recommendations
- Downsize over-provisioned resources

### Caching
- Cache hit ratio target: > 80%
- Use CloudFront for static assets
- Implement multi-tier caching (CDN → Redis → DB)

## Disaster Recovery

### Multi-Region Setup
- Primary: us-east-1 (N. Virginia)
- DR: us-west-2 (Oregon)
- RPO: 5 minutes (async replication)
- RTO: 30 minutes (automated failover)

### Backup Strategy
- PostgreSQL: Automated daily snapshots (35 day retention)
- Redis: Hourly snapshots to S3
- S3: Cross-region replication enabled
- Configurations: Versioned in Git + Parameter Store

## Monitoring & Alerting

### Key Metrics
- CPU utilization per service
- Database connections and queue depth
- WebSocket connection count per server
- Cache hit/miss ratio
- Error rate by endpoint

### Alert Thresholds
- CPU > 80% for 5 minutes → Scale up
- Memory > 85% for 3 minutes → Page on-call
- Error rate > 1% → Trigger incident
- DB connections > 80% → Add connection pool

## Future Improvements

1. **Serverless**: Migrate to Lambda for variable workloads
2. **Global Load Balancing**: Route users to nearest region
3. **Edge Caching**: Cloudflare Workers for API responses
4. **GraphQL Federation**: Microservices with unified schema