# High-Level Design (HLD)

## Overview
This document outlines the high-level architecture for PayScale's High-Throughput Transaction Processing Engine (HTTPE), designed to sustain 12,000+ TPS (burst 18,000 TPS) with a p99 latency of <100ms and 99.99% availability.

## Architecture Components

### 1. API Gateway Layer
*   **Responsibility:** Single entry point for all external client traffic. Handles SSL termination, request routing, rate limiting, and JWT authentication validation.
*   **Interfaces:** Receives HTTPS requests from clients; routes internal traffic via gRPC/HTTP2 to backend services.
*   **Technology Choice:** **Kong API Gateway**. Chosen for its high performance (NGINX-based) and robust plugin ecosystem for rate limiting and auth.
*   **Scaling Strategy:** Horizontally scaled behind an AWS Network Load Balancer (NLB).
*   **Failure Handling:** Trips circuit breakers if downstream services are unresponsive.

### 2. Load Balancer
*   **Responsibility:** Distributes incoming traffic evenly across API Gateway nodes.
*   **Interfaces:** Public internet to API Gateway.
*   **Technology Choice:** **AWS Network Load Balancer (NLB)** for L4 ultra-low latency routing.
*   **Scaling Strategy:** Managed automatically by AWS.
*   **Failure Handling:** Connection draining and automatic health checks to remove dead Gateway nodes.

### 3. Transaction Orchestrator
*   **Responsibility:** Manages the Saga pattern for distributed transactions (e.g., P2P payments). Handles state machine progression, compensation logic (rollbacks), and idempotency checks.
*   **Interfaces:** Subscribes to Kafka topics; communicates with Payment and Account services.
*   **Technology Choice:** **Temporal.io**. Provides durable execution and automatic retries, abstracting away the complexity of distributed state machines.
*   **Scaling Strategy:** Scaled horizontally via Temporal workers.
*   **Failure Handling:** Automatically retries failed steps or executes compensation workflows if terminal failures occur.

### 4. Payment Processing Service
*   **Responsibility:** Core business logic for payments (currency conversion, fee calculation, routing).
*   **Interfaces:** Called by Orchestrator; queries Fraud Service.
*   **Technology Choice:** **Kotlin/Spring Boot**. High performance, non-blocking coroutines, excellent Java ecosystem compatibility.
*   **Scaling Strategy:** Auto-scaling Kubernetes pods based on CPU/Memory and Kafka lag.
*   **Failure Handling:** Implements bulkheads and circuit breakers for external service calls.

### 5. Account Service
*   **Responsibility:** Account CRUD, available/ledger balance management, tier enforcement.
*   **Interfaces:** Direct connection to the sharded PostgreSQL database.
*   **Technology Choice:** **Kotlin/Spring Boot**. 
*   **Scaling Strategy:** Horizontally scaled; utilizes PgBouncer for DB connection pooling.
*   **Failure Handling:** Uses Optimistic Concurrency Control (OCC) to handle concurrent balance updates safely without deadlocks.

### 6. Notification Service
*   **Responsibility:** Dispatches real-time transaction statuses to users via WebSockets, SMS, and Email.
*   **Interfaces:** Consumes `transaction-completed` events from Kafka.
*   **Technology Choice:** **Go (Golang)** + **Firebase Cloud Messaging (FCM)**. Go is exceptionally efficient for maintaining thousands of concurrent WebSocket connections.
*   **Scaling Strategy:** Horizontally scaled stateless nodes.
*   **Failure Handling:** Push notifications are queued; WebSockets gracefully disconnect and auto-reconnect.

### 7. Fraud Detection Service
*   **Responsibility:** Real-time transaction evaluation against velocity rules and ML models.
*   **Interfaces:** Synchronous gRPC calls from Payment Service (15ms SLA).
*   **Technology Choice:** **Python/FastAPI** with **ONNX Runtime** for fast ML inference.
*   **Scaling Strategy:** High-compute CPU/GPU instances in Auto-Scaling Groups.
*   **Failure Handling:** If it breaches the 15ms SLA, a circuit breaker trips, allowing the transaction to proceed but flagged for manual post-review (fail-open).

### 8. Reconciliation Service
*   **Responsibility:** Double-entry bookkeeping verification; detects discrepancies between ledger and available balances.
*   **Interfaces:** Consumes database CDC (Change Data Capture) streams.
*   **Technology Choice:** **Java** batch processing (Spring Batch).
*   **Scaling Strategy:** Runs on a scheduled cron; can spawn parallel workers for large batches.
*   **Failure Handling:** Alerts operations team on any out-of-balance detection.

### 9. Audit & Compliance Service
*   **Responsibility:** Maintains an immutable log of all state transitions and system actions (RBI compliance).
*   **Interfaces:** Consumes all Kafka topics and writes to append-only storage.
*   **Technology Choice:** **Go** writing to **Amazon S3 (WORM enabled)**.
*   **Scaling Strategy:** Simple consumer group scaling.
*   **Failure Handling:** Retries indefinitely; dead-letter queues for unparseable events.

### 10. Message Queue / Event Bus
*   **Responsibility:** Asynchronous inter-service communication; decouples the critical path from secondary processes (notifications, audit).
*   **Interfaces:** Producers (Outbox pattern from DB) and Consumers (various services).
*   **Technology Choice:** **Apache Kafka**.
*   **Scaling Strategy:** Multi-broker cluster partitioned by `account_id` to guarantee event ordering per account.
*   **Failure Handling:** Replication factor of 3, `min.insync.replicas=2` to guarantee zero message loss on broker failure.

### 11. Database Layer
*   **Responsibility:** ACID-compliant, persistent storage of accounts and transactions.
*   **Interfaces:** PgBouncer connection pooler.
*   **Technology Choice:** **PostgreSQL 15 + Citus Extension**.
*   **Scaling Strategy:** Sharded by `account_id` across 4-8 worker nodes.
*   **Failure Handling:** Patroni for automated primary-replica failover (RTO < 30s).

### 12. Cache Layer
*   **Responsibility:** Reduces DB read load; stores rate limits, feature flags, and idempotency keys.
*   **Interfaces:** Queried by API Gateway and all core services.
*   **Technology Choice:** **Redis Cluster**.
*   **Scaling Strategy:** 6-node cluster (3 master, 3 replica).
*   **Failure Handling:** Redis Sentinel automatically promotes a replica if a master fails. Services fallback to database if cache is fully unavailable.

### 13. Observability Stack
*   **Responsibility:** Metrics, distributed tracing, and centralized logging.
*   **Interfaces:** Ingests metrics/logs from all components.
*   **Technology Choice:** **Prometheus + Grafana** (Metrics), **Jaeger** (Tracing), **ELK Stack** (Logs).
*   **Scaling Strategy:** Dedicated monitoring cluster.
*   **Failure Handling:** Monitoring traffic is prioritized lower than transaction traffic to prevent network saturation.
