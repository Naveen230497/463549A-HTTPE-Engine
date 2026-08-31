# ADR 001: Message Queue Selection

**Status:** Accepted

**Context:** 
The current architecture utilizes a single-node RabbitMQ instance which is experiencing severe consumer lag (>30s) and message acknowledgment backlogs at 2,000 TPS (identified as critical bottleneck BN-002). To support the target of 12,000+ sustained TPS and 18,000 burst TPS, we require a messaging infrastructure capable of massive horizontal scalability, strict ordering guarantees, and exactly-once delivery semantics for financial transactional integrity.

**Decision:** 
We will migrate from RabbitMQ to **Apache Kafka**. We will deploy a multi-broker Kafka cluster (minimum 3 brokers) spread across multiple Availability Zones. Kafka will act as the central nervous system for asynchronous transaction processing, utilizing partitioned topics to parallelize processing and consumer groups to scale worker nodes dynamically. We will utilize Kafka's transactional producer API to achieve Exactly-Once Semantics (EOS).

**Alternatives Considered:**
*   **RabbitMQ (Clustered):** While clustering improves availability, RabbitMQ's architecture struggles with the sheer throughput requirements compared to Kafka's append-only log design.
*   **Amazon SQS (Standard):** Cannot guarantee strict ordering or exactly-once delivery.
*   **Amazon SQS (FIFO):** Guarantees ordering and exactly-once processing, but throughput is hard-capped at 3,000 TPS per API action, making it unviable for our 12,000+ TPS requirement.

**Consequences:**
*   **Positive:** Massive throughput capacity; durable event sourcing; exactly-once semantics support.
*   **Negative:** High operational complexity; requires Zookeeper/KRaft management; steep learning curve for the development team lacking prior Kafka experience.

**Compliance:**
Kafka's immutable, append-only log structure aligns perfectly with RBI and PCI-DSS requirements for maintaining complete, auditable transaction histories. Appropriate data retention policies and disk encryption will be enforced on all brokers.
