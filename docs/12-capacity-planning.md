# Capacity Planning & Cost Analysis

## Overview
This document details the infrastructure requirements and cost projections for AWS (Mumbai Region `ap-south-1`) to support the HTTPE architecture at the target 12,000 TPS, ensuring it fits within the strict $45,000/month budget constraint.

## Infrastructure Sizing (12,000 TPS Target)

| Service | Instance Type | vCPU / RAM | Qty | Est. Monthly Cost | Justification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **API Gateway (Kong)** | `c6g.xlarge` | 4 vCPU, 8GB | 8 | $900 | CPU bound (SSL termination). ARM instances (Graviton) offer best price/perf. |
| **Temporal Orchestrator** | `m6g.xlarge` | 4 vCPU, 16GB | 12 | $1,500 | Memory intensive for workflow history. |
| **Payment Service** | `c6g.2xlarge` | 8 vCPU, 16GB | 15 | $3,500 | High compute for business logic and JSON serialization. |
| **Account Service** | `m6g.xlarge` | 4 vCPU, 16GB | 10 | $1,250 | General purpose. |
| **Fraud Detection** | `c6g.4xlarge` | 16 vCPU, 32GB | 8 | $3,800 | Very compute intensive for 15ms ML inference (ONNX). |
| **Notification Service** | `t4g.large` | 2 vCPU, 8GB | 5 | $300 | High network I/O, low CPU. |
| **Kafka Brokers** | `r6g.2xlarge` | 8 vCPU, 64GB | 6 | $3,500 | High RAM for page cache; heavily reliant on EBS gp3 throughput. |
| **Kafka EBS Storage** | `gp3` (3TB) | 1000 MB/s | 6 | $1,800 | 7-day retention for 64 partitions requires significant fast storage. |
| **PostgreSQL (Citus)** | `r6g.4xlarge` | 16 vCPU, 128GB | 14 | $15,500 | 1 Coordinator + 6 Workers (Primary) + 7 Replicas. Highest cost center. DB performance is critical. |
| **PostgreSQL EBS Storage**| `io2` (1TB) | 10k IOPS | 14 | $5,000 | Extreme write IOPS required for WAL and commit logs. |
| **Redis Cluster** | `r6g.xlarge` | 4 vCPU, 32GB | 6 | $1,500 | 3 Master / 3 Replica topology. 96GB total cache. |
| **Observability Stack** | `m6g.2xlarge` | 8 vCPU, 32GB | 4 | $1,000 | Prometheus/Grafana/Jaeger. |
| **Load Balancers (NLB)** | N/A | N/A | 3 | $600 | Data processing fees for high bandwidth. |
| **TOTAL ESTIMATED COST** | | | | **$40,150 / mo** | |

## Cost Optimization Opportunities
The projected cost of **$40,150/month** successfully falls beneath the **$45,000/month** budget ceiling. 
To further optimize costs if required by the CFO:
1.  **Reserved Instances (RIs):** Committing to a 1-year or 3-year term for the massive PostgreSQL and Kafka nodes would reduce their compute costs by 40-60%.
2.  **Spot Instances:** The stateless API Gateway and Notification Service nodes could be placed in Spot Auto-Scaling Groups, reducing their cost by up to 80%, relying on rapid spin-up to handle node terminations.
3.  **Storage Tiering:** Audit logs are moved immediately to S3 Standard-IA (Infrequent Access) or Glacier, which is exponentially cheaper than EBS block storage.
