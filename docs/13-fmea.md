# Failure Mode and Effects Analysis (FMEA)

## Overview
This document analyzes potential failure modes across the HTTPE architecture. Risk Priority Number (RPN) is calculated as **Severity (S) × Occurrence (O) × Detection (D)**, each rated 1-10. An RPN > 200 requires immediate architectural mitigation.

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FM-001** | **Primary Database Shard Crash** | All writes to ~16% of accounts fail. In-flight txns timeout. | 9 | 4 | 2 | **72** | Patroni auto-failover to synchronous replica (<30s RTO). OCC handles retries safely. |
| **FM-002** | **Kafka Broker Failure (1 of 6)** | Temporary partition unavailability; producer latency spikes. | 6 | 5 | 2 | **60** | Replication factor=3, `min.insync.replicas=2`. Cluster self-heals without message loss. |
| **FM-003** | **Redis Cluster Partition / Split-brain** | Idempotency checks fail; rate limits bypassed; cache misses spike. | 8 | 3 | 3 | **72** | Redis Sentinel quorum ensures only the majority partition accepts writes. Circuit breakers open to protect DB from cache stampede. |
| **FM-004** | **Fraud Service Deployment Bug** | 100% of transactions rejected or timeout. | 10 | 2 | 2 | **40** | Canary deployments (1% -> 10% -> 100%). Circuit breaker (CB-FRAUD) fails open if timeouts occur, allowing txns to proceed with a manual review flag. |
| **FM-005** | **AWS AZ-1 Network Partition** | 33% of compute nodes isolated. Cross-AZ latency spikes. | 7 | 3 | 2 | **42** | Multi-AZ deployment (3 AZs). Route53 / NLB automatically drains traffic from isolated AZ. Quorum-based systems (Kafka/DB) continue operating in remaining 2 AZs. |
| **FM-006** | **Idempotency Key Collision** | Legitimate transaction rejected as duplicate (Hash collision). | 8 | 1 | 8 | **64** | Enforce UUIDv4/v7 standard. The probability of collision is mathematically negligible. |
| **FM-007** | **Temporal Orchestrator DB Full** | Cannot start new Sagas; system grinds to halt. | 10 | 2 | 3 | **60** | Aggressive Archival strategy configured in Temporal to move closed workflow histories to S3. High disk-usage alerts at 70%, 80%, 90%. |
| **FM-008** | **Kafka Disk Full** | Broker stops accepting messages; producers crash or block. | 10 | 3 | 2 | **60** | Log compaction enabled for state tables; strict 7-day retention for events. Alerting at 75% volume utilization. |
| **FM-009** | **mTLS Certificate Expiration** | Total inter-service communication failure (Zero Trust breaks). | 10 | 2 | 2 | **40** | Automated certificate rotation via HashiCorp Vault or AWS ACM 15 days prior to expiration. |
| **FM-010** | **Account Service Thread Exhaustion** | 503 errors to Payment Service; cascading timeouts. | 7 | 5 | 2 | **70** | Transitioned to non-blocking Kotlin Coroutines. Bulkhead limits enforced in PgBouncer. |
| **FM-011** | **Poison Pill Message in Kafka** | Consumer crashes repeatedly on same message, blocking partition. | 6 | 6 | 2 | **72** | 3 local retries, then automatic routing to Dead Letter Queue (DLQ) topic, allowing partition processing to continue. |
| **FM-012** | **Clock Skew > 5s across AZs** | JWT validation fails; DB timestamp anomalies. | 6 | 2 | 4 | **48** | Chrony/NTP aggressively syncing with AWS Time Sync Service. Monitoring alerts if skew > 10ms. |
| **FM-013** | **API Gateway Rate Limit Misconfig** | Legitimate users blocked (False Positives). | 5 | 4 | 3 | **60** | Configuration managed via GitOps. Rollback time < 1 minute. |
| **FM-014** | **Database Connection Leak in App** | PgBouncer pool exhausted; new queries block indefinitely. | 8 | 3 | 4 | **96** | Strict ORM/Query builder usage. `idle_in_transaction_session_timeout` enforced at DB level (e.g., 5 seconds) to forcefully kill leaked connections. |
| **FM-015** | **Spike to 30,000 TPS (DDoS / Viral Event)** | System overwhelmed; p99 latency skyrockets to >5 seconds. | 8 | 2 | 1 | **16** | API Gateway sheds load above 18,000 TPS. Queueing absorbs spikes. User receives "System Busy" rather than crashing the database. |
| **FM-016** | **DNS Resolution Failure** | Microservices cannot discover each other; 502 Bad Gateway. | 9 | 2 | 2 | **36** | Implement DNS caching at the Node level (NodeLocal DNSCache) to survive transient Route53 outages. |
| **FM-017** | **Redis Memory Eviction (OOM)** | Cache miss spike; DB connections exhaust under stampede. | 8 | 4 | 2 | **64** | Configure volatile-lru eviction policy. Trigger alerts at 85% memory. |
| **FM-018** | **Temporal Worker Crash** | Sagas stall mid-execution; funds locked in pending state. | 7 | 4 | 3 | **84** | Temporal server maintains state. Restarted workers automatically resume sagas from the last checkpoint. |
| **FM-019** | **Schema Migration Failure** | DB locked; application errors due to missing columns. | 9 | 2 | 3 | **54** | Strict backward-compatible schema changes (e.g., add column nullable first). Liquidbase for rollback. |
| **FM-020** | **Third-Party Payment Gateway Timeout** | Settlement fails or hangs. | 8 | 5 | 2 | **80** | Circuit breaker on external gateways. Asynchronous reconciliation process runs nightly to fix mismatches. |

## Chaos Engineering Experiments

| ID | Fault Injected | Hypothesis | Success Criteria |
| :--- | :--- | :--- | :--- |
| **CE-001** | **Kill Primary Database Node** | System fails over to replica within 30s. | Zero committed txn loss; p99 < 5s during failover. |
| **CE-002** | **500ms Latency to Kafka** | Producer retries increase; no message loss. | Consumer lag recovers within 2 minutes. |
| **CE-003** | **Saturate Redis Cache** | Cache miss rate spikes; circuit breaker protects DB. | DB does not exceed connection limit. |
| **CE-004** | **Kill 50% of Payment Pods** | Remaining pods handle load; auto-scaler spins up replacements. | Error rate < 5%; recovery within 90s. |
| **CE-005** | **Clock Skew (5s)** | Tokens fail validation safely. | No duplicate transactions; self-heals when synced. |
