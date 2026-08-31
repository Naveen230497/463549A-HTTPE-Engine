# Message Queue (Kafka) Topology

## 1. Topic Structure and Partitioning

To support 12,000+ TPS and ensure strict ordering where necessary, we define the following core topics:

| Topic Name | Partitions | Retention | Key Strategy | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `transactions.initiated` | 64 | 7 Days | `transaction_id` | Triggers the Saga orchestrator. |
| `transactions.completed` | 64 | 7 Days | `account_id` | Triggers Notifications. Keyed by account_id to ensure order of notifications per user. |
| `ledger.events` | 128 | 30 Days | `account_id` | Consumed by Reconciliation and Audit services. |
| `settlements.batch` | 16 | 7 Days | `merchant_id` | Triggers batch settlement processing. |
| `audit.log` | 128 | Infinite (Compacted) | `entity_id` | Append-only log of all system state changes for RBI compliance. |

**Partition Math (12k TPS):**
*   Target throughput = 12,000 TPS.
*   Assuming a single consumer instance can process 200 msg/sec.
*   Required consumers = 12,000 / 200 = 60 consumers.
*   We use **64 partitions** for core transaction topics to allow up to 64 consumer pods in a Consumer Group, providing slightly more than the required parallelism.

## 2. Exactly-Once Semantics (EOS)
We cannot simply update the database and then `kafka.produce()` because if the application crashes between the two steps, the database commits but the event is lost (Dual-Write Problem).

**Implementation:** We use the **Transactional Outbox Pattern** combined with **Change Data Capture (CDC)** via Debezium.
1. The Account Service writes the state change to the `accounts` table AND inserts an event record into an `outbox` table in the *same local database transaction*.
2. A Debezium connector tails the PostgreSQL WAL (Write-Ahead Log) and streams the outbox records into Kafka with Exactly-Once guarantees.

## 3. Consumer Group Topology
*   **NotificationServiceGroup:** Subscribes to `transactions.completed`. Auto-scales up to 64 pods.
*   **AuditServiceGroup:** Subscribes to `audit.log`. Writes to S3 in large batches.
*   **ReconciliationGroup:** Subscribes to `ledger.events`.

## 4. Dead Letter Queue (DLQ) Strategy
If a message fails processing (e.g., malformed JSON, downstream API down):
1.  **Local Retries:** The consumer retries up to 3 times with exponential backoff (e.g., 1s, 2s, 4s).
2.  **DLQ Topic:** If all retries fail, the message is published to a specific DLQ topic (e.g., `transactions.completed.dlq`) and the consumer commits the offset to unblock the partition.
3.  **Alerting:** An alert is fired if DLQ depth > 0.
4.  **Reprocessing:** A separate administrative tool allows operators to inspect DLQ messages and manually requeue them to the main topic once the underlying bug is fixed.
