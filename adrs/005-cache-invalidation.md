# ADR 005: Cache Invalidation Strategy

**Status:** Accepted

**Context:** 
To reduce the read load on the PostgreSQL database and achieve sub-30ms p50 latency, we use a Redis Cluster. However, caching mutable data (like user profiles, KYC status, and merchant configurations) introduces the classic cache invalidation problem. Stale data in a financial system can lead to compliance violations (e.g., allowing a transaction for a user whose KYC just expired).

**Decision:** 
We will implement a **Cache-Aside pattern with TTLs**, combined with **Event-Driven Write-Through invalidation**.
1. **Cache-Aside:** When reading data, the application checks Redis. If miss, it queries PostgreSQL, writes the result to Redis with a TTL (e.g., 5 minutes), and returns.
2. **Event-Driven Invalidation:** When a service updates a record in the database, it publishes an `entity_updated` event to Kafka. A dedicated Cache Invalidator worker consumes these events and issues a `DEL` command to Redis for the corresponding key.

**Alternatives Considered:**
*   **Write-Through (Synchronous):** The application updates the DB and Redis synchronously. Rejected because if the Redis update fails after the DB commit, data is inconsistent.
*   **Write-Behind:** Application writes only to Redis; Redis flushes to DB. Rejected for core financial data due to the risk of data loss if Redis crashes before flushing.

**Consequences:**
*   **Positive:** High read throughput; eventual consistency is bounded by both the TTL (worst-case scenario) and the Kafka event pipeline (usually <100ms).
*   **Negative:** Eventual consistency means there is a tiny window (<100ms) where a read might return stale data after an update. For operations requiring absolute strong consistency (like balance checks before a debit), we will bypass the cache entirely and read directly from the PostgreSQL primary node.

**Compliance:**
Balances are never cached for transactional authorization; they are always read directly from the DB under OCC. Caching is restricted to metadata, idempotency keys, and fraud rule configurations.
