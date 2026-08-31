# ADR 002: Database Selection

**Status:** Accepted

**Context:** 
The existing monolithic PostgreSQL 15 database is experiencing critical connection pool exhaustion (BN-001) and severe row-level locking contention (BN-006) on the `accounts` table at just 1,800 TPS. Achieving 12,000+ TPS requires distributing the data layer to avoid a single point of failure and single-node I/O bottlenecks, all while remaining within a $45,000/month total infrastructure budget.

**Decision:** 
We will implement a sharded database architecture using **PostgreSQL with the Citus extension**. This allows us to horizontally partition (shard) our massive `accounts` and `transactions` tables across multiple worker nodes while querying them through a coordinator node as if they were a single database. We will utilize an intermediate connection pooler (PgBouncer) to multiplex the 2,000+ application connections down to a manageable number of database connections.

**Alternatives Considered:**
*   **CockroachDB:** Offers excellent out-of-the-box distributed SQL capabilities and strong consistency. Rejected due to potentially higher infrastructure and licensing costs that could threaten our budget constraints, as well as the team's lack of operational experience with it.
*   **TiDB:** A powerful HTAP database, but the architecture (PD, TiKV, TiDB nodes) introduces significant operational overhead compared to scaling our known PostgreSQL stack.
*   **NoSQL (e.g., MongoDB, Cassandra):** Rejected. While highly scalable, financial systems require strict ACID compliance and complex relational queries (like double-entry reconciliation) which are exceedingly difficult to enforce in eventually consistent NoSQL stores.

**Consequences:**
*   **Positive:** Leverages existing team expertise in PostgreSQL; avoids expensive enterprise licenses; provides linear horizontal scalability.
*   **Negative:** Requires careful selection of a shard key (e.g., `account_id`) to ensure even data distribution and avoid cross-shard JOINs which degrade performance.

**Compliance:**
All PostgreSQL nodes will be provisioned in AWS `ap-south-1` (Mumbai) to strictly adhere to the RBI Data Localization Directive. Data will be encrypted at rest using AES-256 via AWS KMS.
