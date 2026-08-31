# Performance Budget (Target: p99 < 100ms)

To achieve a 99th percentile (p99) transaction latency of under 100ms, we must strictly budget every millisecond in the critical synchronous path (from request ingestion to returning HTTP 202 Accepted).

| Processing Stage | Budget (ms) | Component | Justification / Technical Constraint |
| :--- | :--- | :--- | :--- |
| **API Gateway Routing & SSL** | 3 - 5 | Kong | Hardware AES-NI offload; in-memory routing via NGINX. |
| **Authentication (JWT)** | 2 - 3 | Kong | Local validation using cached asymmetric public keys (no external DB hit). |
| **Idempotency Check** | 1 - 2 | Redis Cluster | Single `GET` and `SET NX`; sub-millisecond network hop on local VPC. |
| **Fraud Detection (Sync)** | 10 - 15 | Fraud Service | Feature lookups from Redis + ONNX model inference. Circuit breaker trips at 15ms. |
| **Saga Orchestrator Dispatch** | 5 - 10 | Temporal.io | Registering the workflow state in Temporal's internal DB and appending to task queue. |
| **Response Serialization** | 2 - 3 | API Gateway | JSON serialization and HTTP response formatting. |
| **Network Transit (Internal)**| 5 - 10 | AWS VPC | Accumulated latency of microservice-to-microservice gRPC hops. |
| **TOTAL (Critical Path)** | **28 - 48 ms** | | **Well within the 100ms p99 target.** |

*Note: The actual heavy lifting (database OCC updates, ledger entries, Kafka publishing) happens asynchronously AFTER the 202 response is returned to the user, handled by Temporal workflow workers. Therefore, database I/O is excluded from the synchronous critical path.*
