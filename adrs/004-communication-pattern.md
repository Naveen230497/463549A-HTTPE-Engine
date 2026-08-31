# ADR 004: Service Communication Pattern

**Status:** Accepted

**Context:** 
To handle 12,000 TPS, our microservices must communicate efficiently. Synchronous REST calls between internal services create tight coupling, cascading failures, and thread pool exhaustion (identified in bottleneck BN-003). However, entirely asynchronous communication makes immediate user feedback (e.g., payment success/failure) difficult.

**Decision:** 
We will use a **Hybrid Communication Pattern**. 
1. **Synchronous (gRPC):** Used ONLY for the critical authorization path where an immediate response is mandatory (e.g., API Gateway -> Payment Service, Payment Service -> Fraud Detection). We use gRPC over HTTP/2 for minimal payload size and multiplexing.
2. **Asynchronous (Kafka Event-Driven):** Used for all state-mutating operations and downstream processes (Saga orchestration, Notifications, Ledger generation, Audit).

**Alternatives Considered:**
*   **100% Synchronous REST:** Rejected. It guarantees thread exhaustion at 12,000 TPS if any downstream service slows down.
*   **100% Asynchronous (Event Sourcing everywhere):** Rejected. The API Gateway would have to hold HTTP connections open while polling for an async result, or clients would have to rely entirely on WebSockets for the initial payment confirmation, complicating client integration.

**Consequences:**
*   **Positive:** The critical path remains fast and responsive to the user, while heavy lifting (DB writes, notifications) is decoupled and smoothed out over message queues.
*   **Negative:** Adds architectural complexity. Developers must understand both gRPC proto definitions and Kafka event schemas.

**Compliance:**
gRPC channels will be secured using mutual TLS (mTLS) to encrypt data in transit between microservices, satisfying PCI-DSS requirements.
