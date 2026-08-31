# Technology Evaluation Matrix

## 1. Database Selection (Distributed SQL / Relational)

| Criteria | PostgreSQL + Citus | CockroachDB | TiDB |
| :--- | :--- | :--- | :--- |
| **Architecture** | Master-worker with sharding | Masterless, horizontally scalable | Distributed HTAP (MySQL compatible) |
| **Performance (12k TPS)**| High (requires careful shard key) | High (automatic sharding/rebalancing)| High (scales horizontally well) |
| **Operational Complexity**| Medium (requires managing Citus nodes)| Low (built for easy scaling) | High (complex architecture, PD, TiKV) |
| **Cost** | Low (Open Source, standard VMs) | High (Enterprise features expensive) | Medium |
| **Team Expertise** | High (Team already knows PostgreSQL)| Medium (PostgreSQL wire compatible)| Low (MySQL ecosystem) |
| **Decision** | **Selected** | Rejected | Rejected |

**Rationale:** The team already has deep expertise in PostgreSQL. Citus provides the necessary horizontal scaling capabilities (sharding) while allowing us to retain our existing PostgreSQL tooling and knowledge.

## 2. Message Queue Selection

| Criteria | Apache Kafka | RabbitMQ | Amazon SQS |
| :--- | :--- | :--- | :--- |
| **Architecture** | Distributed commit log | Smart broker, dumb consumer | Managed queue service |
| **Throughput** | Extremely High (100k+ TPS) | Medium (Bottlenecks at high load) | High (Managed auto-scaling) |
| **Exactly-Once Semantics**| Yes (Transactional API) | No (Requires custom deduplication)| No (Standard), Yes (FIFO - limited TPS)|
| **Data Retention** | Persistent (Disk-based logs) | Transient (In-memory/Disk limits) | Up to 14 days |
| **Cost** | Medium (Infrastructure overhead) | Low | High at extreme scale |
| **Decision** | **Selected** | Rejected | Rejected |

**Rationale:** RabbitMQ is already failing at 2,000 TPS (BN-002). Kafka is designed for exactly this scale, providing distributed partitions, exactly-once semantics (crucial for financial transactions), and replayable event logs for auditing.

## 3. Cache Layer Selection

| Criteria | Redis Cluster | Memcached | Hazelcast |
| :--- | :--- | :--- | :--- |
| **Data Structures** | Rich (Hashes, Sets, Lists, Bitmaps) | Simple (Key-Value strings) | Rich (Java-centric) |
| **Persistence** | Yes (RDB / AOF) | No | Yes |
| **Throughput** | High | High | High |
| **High Availability** | Yes (Sentinel / Cluster) | Client-side only | Yes |
| **Decision** | **Selected** | Rejected | Rejected |

**Rationale:** Redis Cluster provides the necessary distributed caching architecture, high availability, and rich data structures (useful for rate limiting and complex state storage) needed to alleviate database read pressure.
