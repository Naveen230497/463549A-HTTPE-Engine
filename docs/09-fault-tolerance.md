# Fault Tolerance & Resilience Design

## Overview
To achieve 99.99% availability (max 52.6 minutes of downtime per year), the HTTPE architecture must aggressively protect itself against partial system failures. A failure in a downstream component (like the Fraud Service or a Database Shard) must not cause cascading thread exhaustion across the API Gateway or Payment Service.

## 1. Circuit Breakers
We implement the Circuit Breaker pattern for all synchronous inter-service calls.
*   **CB-FRAUD:** Protects the Payment Service from Fraud Service timeouts. If 3 timeouts occur within 10s, the circuit OPENS. Fallback behavior: allow transaction but append an "AWAITING_MANUAL_REVIEW" flag. Reset timeout: 15s.
*   **CB-DB-PRIMARY:** Protects application from dead DB connections. 2 failures in 5s opens the circuit. Fallback: Queue writes to Kafka (if feasible for that flow) or immediately return 503 Service Unavailable to client rather than holding the connection open.
*   **Implementation:** See `pseudocode/circuit-breaker.py` and `diagrams/circuit-breaker-fsm.puml`.

## 2. Bulkhead Isolation
To prevent a spike in one transaction type from starving others, we implement Bulkheads at the connection pool and thread pool level.
*   **Thread Pools:** Dedicated thread pools in the API Gateway for P2P vs. Merchant transactions. A DDoS attack on Merchant APIs will not exhaust threads needed for P2P.
*   **Database Connections:** PgBouncer enforces hard limits per service. The Notification service cannot consume more than 5% of database connections, ensuring core payment flows are never starved.

## 3. Idempotency handling
Idempotency ensures that network retries do not result in duplicate transactions.
*   **Mechanism:** The client generates a unique `idempotency_key` (UUIDv4) for every POST request.
*   **Storage:** Redis Cluster (Fast, 24-hour TTL).
*   **Flow:** The API Gateway intercepts the request, checks Redis. If the key exists, it returns the stored HTTP response. If not, it processes the transaction, then stores the response payload in Redis keyed by the `idempotency_key`.
*   **Implementation:** See `pseudocode/idempotency-handler.py`.

## 4. Timeout and Retry Policies
*   **Synchronous Calls:** Strict aggressive timeouts. (e.g., Fraud evaluation timeout = 15ms). No retries on synchronous POST operations unless specifically idempotent.
*   **Asynchronous Calls:** Kafka consumers retry indefinitely for infrastructure errors (DB down), but move to DLQ for payload errors (malformed JSON). Exponential backoff (1s, 2s, 4s, 8s, 16s) is used to prevent retry storms.
