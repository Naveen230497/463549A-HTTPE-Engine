# Data Flow Design

## Overview
This document describes the critical data flows for the High-Throughput Transaction Processing Engine (HTTPE). It maps the interactions depicted in the associated Sequence Diagrams (`/diagrams/*.puml`) and details the error handling, compensation logic, and asynchronous versus synchronous communication boundaries.

## 1. P2P Payment Transaction Flow
**Nature:** Hybrid (Synchronous for authorization, Asynchronous for fulfillment and notification).

**Flow Description:**
1.  **Initiation:** The client sends an HTTPS POST request with an `idempotency_key`.
2.  **Idempotency Check (Sync):** The Payment Service checks Redis. If the key exists, the cached response is returned, preventing double charges.
3.  **Fraud Evaluation (Sync):** A fast gRPC call (<15ms) to the Fraud Service. If it timeouts, the circuit breaker defaults to a 'fail-open' (allow but flag) behavior.
4.  **Saga Execution (Async Orchestration):** Temporal.io orchestrates the distributed transaction:
    *   **Debit Sender:** Account Service uses Optimistic Concurrency Control (OCC) to debit the sender.
    *   **Credit Receiver:** Account Service credits the receiver using OCC.
    *   **Ledger Entries:** Creates immutable double-entry bookkeeping records.
5.  **Compensation (Failure Case):** If the *Credit Receiver* step fails (e.g., account frozen), Temporal automatically invokes the compensation step: *Credit Sender* (refund the debited amount) and marks the transaction as `FAILED`.
6.  **Completion (Async):** Upon success, the orchestrator notifies the Payment Service. An event is published to Kafka (`transaction_completed`).
7.  **Notification (Async):** The Notification Service consumes the Kafka event and pushes a WebSocket update to the clients.

## 2. Batch Merchant Settlement Flow
**Nature:** Fully Asynchronous Batch Process.

**Flow Description:**
1.  **Trigger:** A cron job triggers the Settlement Service.
2.  **Data Fetch:** Retrieves up to 100,000 `PENDING` merchant settlement records.
3.  **Batch Processing:** Processes records in chunks of 1,000.
4.  **Transaction Integrity:** The Account Service wraps each chunk in a database transaction (`BEGIN` ... `COMMIT`). It aggregates funds from the central settlement pool, credits the merchant accounts, updates the status to `COMPLETED`, and writes ledger entries.
5.  **Failure Case:** If a chunk fails, the DB transaction rolls back. The Settlement Service logs the error and retries the chunk with exponential backoff.
6.  **Completion:** Upon finishing the batch, an event is published to Kafka, triggering email reports to merchants via the Notification Service.

## 3. Database Failover Flow
**Nature:** Infrastructure Level.

**Flow Description:**
1.  **Detection:** Patroni monitors the PostgreSQL Primary. If the primary crashes, the heartbeat to the Distributed Configuration Store (DCS, e.g., Consul/Etcd) drops.
2.  **Promotion:** Patroni promotes the synchronous Read Replica to Primary.
3.  **Routing Update:** The DCS updates the leader IP address. PgBouncer detects the configuration change and routes new incoming queries to the newly promoted Primary.
4.  **Client Impact:** In-flight transactions during the ~30s failover window will encounter connection drops or timeouts. The Payment Service / Temporal orchestrator will automatically retry these transactions. Because we use Idempotency Keys and OCC, these retries are perfectly safe and will not result in double-spending.
