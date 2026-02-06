# Data Flow Architecture

## Overview
CloudSync uses an event-driven architecture to propagate data changes in real-time across connected clients.

## High-Level Data Flow

```
Client A          CloudSync Platform          Client B
   |                      |                       |
   |---- Data Change ---->|                       |
   |                      |-- WebSocket Event --->|
   |                      |                       |
   |<--- Confirmation ----|                       |
   |                      |-- Conflict Check --->|
   |                      |<-- Resolution --------|
   |<-- Sync Complete -----|                       |
```

## Detailed Flow

### 1. Change Detection
Every write to PostgreSQL triggers a function that:
- Captures the operation (INSERT/UPDATE/DELETE)
- Records the table name and primary key
- Serializes the row data to JSON
- Publishes to Redis pub/sub channel `db_changes`

### 2. Event Processing
Celery workers subscribe to Redis and:
- Parse the change event
- Identify affected clients via connection registry
- Determine sync strategy (real-time vs batch)
- Queue WebSocket messages for delivery

### 3. Conflict Resolution
When concurrent edits occur:
- Timestamp-based: Last-write-wins (default)
- Operational Transform: For collaborative text editing
- Manual merge: Flag for user review (configurable)

### 4. Delivery
WebSocket servers (running on EC2):
- Maintain persistent connections (up to 10k per instance)
- Send JSON payloads with change metadata
- Handle acknowledgments and retries
- Auto-reconnect on connection loss

## Event Types

| Event | Description | Payload Size |
|-------|-------------|--------------|
| `data.create` | New record created | ~2KB |
| `data.update` | Existing record modified | ~1KB (delta) |
| `data.delete` | Record removed | ~100B |
| `sync.batch` | Multiple changes batched | Up to 100KB |
| `conflict.detected` | Manual resolution needed | ~500B |

## Latency Targets

- **Change detection**: < 10ms (PostgreSQL trigger)
- **Event processing**: < 50ms (Celery + Redis)
- **Client delivery**: < 100ms (WebSocket)
- **End-to-end**: < 200ms (p95)

## Failure Handling

### Redis Unavailable
- Events queued in PostgreSQL `pending_events` table
- Background worker processes queue when Redis recovers

### WebSocket Server Down
- Events buffered in Redis (max 1 hour)
- Clients reconnect to healthy server
- Missed events replayed from buffer

### Client Offline
- Events stored in "outbox" pattern
- Sync occurs when client reconnects
- Differential sync (only missed changes)

## Monitoring

Key metrics tracked in Datadog:
- `sync.latency.p95`: End-to-end sync time
- `conflict.rate`: Conflicts per minute
- `websocket.connections.active`: Current connections
- `redis.pubsub.backlog`: Pending events

## Scaling Considerations

### Horizontal Scaling
- WebSocket servers: Add EC2 instances behind ALB
- Celery workers: Scale ECS tasks based on queue depth
- Database: Read replicas for analytics, write replicas for HA

### Partitioning
- Redis pub/sub sharded by user_id % 16
- WebSocket connections hashed to specific servers
- Database partitioned by tenant (for enterprise plan)

## Security

- WebSocket connections require valid JWT
- Events encrypted with AES-256 before Redis storage
- Client IDs verified against connection registry
- Audit log tracks all sync events (retained 30 days)