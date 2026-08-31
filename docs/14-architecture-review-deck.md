# Architecture Review Board (ARB) Presentation Outline

## Slide 1: Title & Executive Summary
*   **Project:** High-Throughput Transaction Processing Engine (HTTPE)
*   **Mission:** Scale PayScale's infrastructure from 1,200 TPS to 12,000+ TPS to support the Diwali campaign.
*   **Key Results:** 12k sustained TPS, <100ms p99 latency, 99.99% Availability, $40,150/mo cost.

## Slide 2: The Monolithic Bottleneck (Problem Statement)
*   Current architecture uses a single PostgreSQL instance and single RabbitMQ node.
*   **Load Test Failures:** Connection exhaustion at 1,800 TPS, Consumer lag >30s at 2,000 TPS, 15% database deadlock rate.
*   **Conclusion:** Vertical scaling is dead. We must distribute.

## Slide 3: High-Level Architecture
*   *(Insert `system-architecture.png` here)*
*   **Ingress:** Kong API Gateway + AWS NLB.
*   **Core:** Kotlin microservices.
*   **State & Orchestration:** Temporal.io for Saga execution.
*   **Event Bus:** Apache Kafka (6 brokers, 64 partitions).
*   **Database:** PostgreSQL 15 + Citus (Hash-Sharded).

## Slide 4: Database Sharding Strategy (Solving BN-001)
*   **Strategy:** Hash-based sharding on `account_id`.
*   **Topology:** 6 Citus worker nodes (+6 replicas for HA).
*   **Why Hash?** Ensures mathematically even distribution of data and CPU load, preventing hot partitions.
*   **The Catch:** P2P transactions cross shards. We cannot use local ACID transactions for P2P.

## Slide 5: The Saga Pattern & Concurrency (Solving BN-006)
*   Since P2P crosses shards, we use **Temporal.io** to orchestrate a distributed Saga.
*   Step 1: Debit Sender (Shard A). Step 2: Credit Receiver (Shard B).
*   If Step 2 fails, Temporal automatically executes the Compensation transaction (Credit Sender).
*   **Lock-Free Execution:** Replaced pessimistic locking with Optimistic Concurrency Control (OCC). Row versions are checked at commit time, eliminating deadlocks entirely.

## Slide 6: Fault Tolerance & Idempotency
*   **Network Retries:** Solved via Redis-backed `X-Idempotency-Key` tracking. 24h TTL.
*   **Circuit Breakers:** Fraud Service has a strict 15ms timeout. If it breaches, the Circuit Breaker trips to `OPEN`, failing-open to allow the transaction but flagging it for review.
*   **Database HA:** Patroni manages PostgreSQL. <30s RTO.

## Slide 7: Capacity Plan & Budget Constraints
*   **Budget Ceiling:** $45,000 / month.
*   **Our Plan:** $40,150 / month at 12,000 TPS.
*   Heaviest investments are in the Data Tier (Citus Nodes) and Event Tier (Kafka).
*   Further optimization possible via AWS Reserved Instances.

## Slide 8: Q&A Preparedness
*(Back pocket slides for ARB Questions)*
*   *What if Kafka goes down?* -> Replication Factor 3, min.insync=2. Total cluster failure means API Gateway sheds load (503).
*   *What about Write-Skew?* -> OCC explicitly prevents this.
*   *How do you handle merchant settlements?* -> Asynchronous cron job processing 1,000 records per DB transaction chunk.
