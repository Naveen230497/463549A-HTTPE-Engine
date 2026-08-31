# ADR 003: Database Sharding Strategy

**Status:** Accepted

**Context:** 
To handle 12,000 TPS, our PostgreSQL database must be distributed horizontally. We need to determine the Shard Key, which dictates how data is distributed across the database nodes. A poor shard key will result in uneven data distribution (hot spots) or excessive cross-shard queries, both of which severely degrade performance.

**Decision:** 
We will use **Hash-Based Sharding** with `account_id` as the primary shard key for the `accounts` table, and co-locate related `transactions` and `ledger_entries` using the same `account_id` (specifically `source_account_id` for P2P transactions). 
The hashing algorithm (e.g., Jenkins hash) will map `account_id` uniformly across N available shards.

**Alternatives Considered:**
*   **Shard by `user_id`:** A user might have multiple accounts (e.g., Savings, Wallet). Sharding by `user_id` co-locates a user's accounts, making queries fetching all user accounts fast. However, it doesn't solve cross-user P2P payments (which still require cross-shard coordination) and could create hot spots if a merchant user has exceptionally high volume.
*   **Geographic Sharding (Range-Based):** Sharding by region (e.g., North India, South India). Rejected because financial transactions frequently cross geographic boundaries, leading to many cross-shard queries. Additionally, population density differences lead to severe shard imbalance.
*   **Range-Based by `account_id`:** Rejected because it naturally leads to hot-spots on the newest shard where new, highly active accounts are continuously inserted.

**Consequences:**
*   **Positive:** Hash-based sharding guarantees near-perfect uniform distribution of data and load across all nodes, preventing hot partitions.
*   **Negative:** P2P transactions between Account A and Account B will likely fall on different shards. This means a single database transaction cannot update both accounts atomically.

**Mitigation for Cross-Shard Transactions:**
Because P2P payments require cross-shard coordination, we MUST use the **Saga Pattern** (orchestrated by Temporal) rather than a traditional Two-Phase Commit (2PC), which holds locks too long and kills throughput. The Saga will execute the debit on Shard 1, and the credit on Shard 2 as independent, idempotent local transactions.
