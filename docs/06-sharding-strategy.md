# Database Sharding Strategy & Capacity Plan

## 1. Shard Key Selection
As defined in `ADR-003`, we utilize **hash-based sharding on `account_id`**.
`shard_id = hash(account_id) % num_shards`

## 2. Shard Count & Topology
To calculate the required shards for 12,000 TPS:
*   A well-tuned PostgreSQL node on modern hardware (e.g., AWS `r6g.2xlarge`, 8 vCPU, 64GB RAM, io2 block express NVMe) can comfortably handle ~4,000 transactional writes per second.
*   Target = 12,000 TPS.
*   Minimum required = 12,000 / 4,000 = 3 Shards.
*   Factoring in the 18,000 TPS Burst requirement and safe capacity headroom (50% max utilization target), we require **6 Shard Nodes**.
*   **Topology:** 1 Citus Coordinator Node + 6 Worker Nodes. Each Worker Node has 1 synchronous Read Replica for high availability (Total 12 database instances).

## 3. Cross-Shard Transactions
In a P2P transfer, Sender A (Shard 2) sends money to Receiver B (Shard 5).
A traditional SQL `BEGIN...COMMIT` cannot span Shard 2 and 5 without crippling distributed locks (Two-Phase Commit).
Instead, we rely on the **Saga Pattern**:
1.  Orchestrator requests Debit from Shard 2.
2.  Shard 2 performs local ACID transaction: debits A, writes local ledger entry.
3.  Orchestrator requests Credit to Shard 5.
4.  Shard 5 performs local ACID transaction: credits B, writes local ledger entry.
If step 4 fails, Orchestrator executes a compensating transaction on Shard 2 to refund A.

## 4. Shard Rebalancing (Scaling Out)
When the system approaches 70% capacity, we must add shards. Citus provides an Enterprise Rebalancer feature, but for an open-source approach:
1.  Provision 2 new Worker Nodes (total 8).
2.  The hashing algorithm uses Consistent Hashing. Only `1/N` of the data (where N=8) needs to move.
3.  Citus logically copies tenant chunks from old nodes to new nodes in the background using logical replication.
4.  Once synchronized, Citus briefly takes a fast lock, updates routing tables on the Coordinator, and drops the old chunks. 
5.  Expected latency impact: Minor jitter during the final cutover lock (usually <200ms).

## 5. Routing Layer
Application connections do not route to shards directly. They connect to PgBouncer, which routes to the Citus Coordinator node. The Coordinator maintains the metadata table (`pg_dist_partition`) and automatically rewrites incoming queries, dispatching them to the correct Worker Node based on the `WHERE account_id = X` clause.

## 6. Failure Handling
If Worker Node 3 crashes:
*   Patroni detects the crash via consensus loss.
*   Patroni promotes Worker Node 3's replica to Primary.
*   The connection pooler routes traffic to the new Primary.
*   RTO is <30 seconds. In-flight cross-shard transactions managed by Temporal will gracefully retry or compensate.

## 7. Data Locality
All shards, replicas, and backups are strictly provisioned in AWS `ap-south-1` (Mumbai). No cross-region replication is utilized outside of India to guarantee absolute compliance with the RBI Data Localization Directive. Multi-AZ (Availability Zone) deployment within the Mumbai region provides disaster recovery without violating locality constraints.
