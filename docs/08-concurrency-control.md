# Concurrency Control & Distributed Locking

## 1. The Challenge: Concurrency in Fintech
In a High-Throughput Transaction Processing Engine (HTTPE), thousands of requests can hit the same account simultaneously (e.g., a popular merchant receiving payments). If we use standard pessimistic locking (`SELECT ... FOR UPDATE`), transactions line up sequentially. At 12,000 TPS, this creates massive thread pools, queue depths, and eventual timeouts (as seen in Bottleneck BN-006).

## 2. Optimistic Concurrency Control (OCC)
We use OCC to achieve lock-free balance updates. Every account has a `version` column.

**How it works:**
1. Read the account balance and current version (e.g., balance=1000, version=1).
2. Validate business rules (e.g., 1000 - 200 >= 0).
3. Execute the update, explicitly checking the version: 
   `UPDATE accounts SET balance = 800, version = 2 WHERE account_id = X AND version = 1`
4. If another transaction updated the account in the milliseconds between step 1 and 3, the `version` will no longer be 1. The database will return `0 rows updated`.
5. The application catches this, fetches the new balance and version, and retries the operation from step 1.

**Why this prevents Write-Skew:**
Write-skew occurs when two transactions read overlapping data and make disjoint updates based on stale reads. Because OCC explicitly checks the `version` at the exact moment of the write, it is mathematically impossible for a write to succeed if the underlying data has changed since the read. See `pseudocode/occ-balance-update.py` for the implementation.

## 3. Distributed Locking (Fencing Tokens)
While OCC handles single-row concurrency, some operations require cross-system locks (e.g., running the cron job for Merchant Settlements). To prevent two instances of the Settlement Cron from running simultaneously, we use Distributed Locking via Redis (Redlock pattern).

**Fencing Tokens:**
To prevent split-brain scenarios (where a worker pauses, loses its lock, but wakes up and writes to the DB anyway), the distributed lock service generates a monotonically increasing **Fencing Token** when a lock is acquired. The database validates this token; if a worker tries to write using an older token than what the DB has already seen, the write is rejected.

## 4. Isolation Levels
We enforce strict isolation levels depending on the query to balance correctness and performance:

| Query Type | Isolation Level | Justification |
| :--- | :--- | :--- |
| **Balance Debit/Credit** | `READ COMMITTED` | Because we use OCC (which enforces correctness at the row level via the version check), we do not need the database to enforce heavy `SERIALIZABLE` locks. `READ COMMITTED` provides maximum throughput. |
| **Settlement Batch** | `SERIALIZABLE` | Aggregating thousands of rows requires absolute consistency to ensure no concurrent updates corrupt the sum. |
| **Dashboard Queries** | `READ COMMITTED` (Replica) | Dashboards querying read-replicas accept slight staleness (ms) for performance. |
| **Reconciliation** | `SNAPSHOT ISOLATION` | Needs a consistent point-in-time view of the entire database to sum debits vs credits without blocking writers. |
