# Load Testing Strategy

## Overview
To validate the architecture's capability to handle 12,000 sustained TPS and 18,000 burst TPS, we will use **k6** (a modern, Go-based load testing tool) to simulate real-world traffic patterns.

## 1. Test Scenarios
1.  **Baseline (LT-001):** 1,200 TPS for 30 min. *Goal: Establish current system baseline.*
2.  **Target Load (LT-002):** 12,000 TPS for 60 min. *Goal: Validate the new architecture meets the core requirement.*
3.  **Burst Capacity (LT-003):** 18,000 TPS for 15 min. *Goal: Validate Auto-Scaling Groups and connection pool headroom.*
4.  **Soak Test (LT-004):** 9,600 TPS for 4 hours. *Goal: Detect memory leaks in JVM services or unacknowledged Kafka messages.*
5.  **Failover Under Load (LT-006):** 12,000 TPS. At T+10m, kill a primary database shard. *Goal: Validate <30s RTO and OCC retry logic.*
6.  **Hot Partition (LT-008):** 5,000 TPS directed at a single Merchant Account. *Goal: Test the upper bounds of OCC contention on a single row.*

## 2. Pass / Fail Criteria (For Target Load LT-002)
*   **Latency:** p50 < 50ms, p99 < 100ms.
*   **Error Rate:** HTTP 5xx errors < 0.01%.
*   **Resource Utilization:** CPU/Memory across all pods < 75% (maintaining headroom).
*   **Message Queue:** Kafka consumer lag must not consistently grow (must plateau).

## 3. Metrics Collection
All k6 metrics will be streamed directly to an InfluxDB instance and visualized in Grafana overlaying the application metrics (Prometheus).
*   `http_req_duration`: End-to-end latency.
*   `http_req_failed`: Error rate.
*   `db_deadlocks` (Prometheus): Must remain 0 (due to OCC).
*   `occ_retries` (Prometheus): Expected to be non-zero, but must not exceed 2% of total transactions.
7.  **Spike Test (LT-005):** 25,000 TPS for 2 minutes. *Goal: Observe system degradation during extreme viral events and verify API Gateway sheds load.*
8.  **Database Failover Soak (LT-007):** 5,000 TPS while cycling DB primary nodes every 30 minutes for 2 hours. *Goal: Verify no long-term connection pool exhaustion after repeated failovers.*
