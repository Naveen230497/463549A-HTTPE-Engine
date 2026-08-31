# Database Schema Design

## Overview
This document outlines the database schema design for the PayScale HTTPE project, tailored for PostgreSQL 15 running with the Citus sharding extension. The schema strictly enforces ACID constraints, maintains an immutable ledger for RBI compliance, and utilizes Optimistic Concurrency Control (OCC) to guarantee high throughput without deadlocks.

## Entity Relationship Diagram
The full ERD is defined in `schemas/erd/erd-diagram.dbml`. You can render it visually by pasting the contents into [dbdiagram.io](https://dbdiagram.io).

## Key Design Principles
1.  **UUIDv7 Primary Keys:** Standard UUIDv4 causes index fragmentation in B-Tree indexes because the values are entirely random. UUIDv7 includes a time-ordered prefix, ensuring that new rows are appended sequentially to the index, vastly improving write throughput.
2.  **Optimistic Concurrency Control (OCC):** The `accounts` table uses a `version` column. Every debit/credit must include `WHERE version = X`. If the row is updated by a concurrent transaction, the DB returns 0 rows updated, and the application orchestrator retries safely.
3.  **Strict Constraints:** Negative balances are prevented at the database level (`CHECK (available_balance >= 0)`) to ensure consistency even if application-level logic fails.

## Indexing Strategy
*   **`transactions(idempotency_key)`:** UNIQUE B-Tree index. Crucial for fast idempotency lookups and preventing duplicate records.
*   **`accounts(user_id)`:** B-Tree index to allow fast retrieval of all accounts belonging to a specific user.
*   **`transactions(source_account_id)` & `transactions(destination_account_id)`:** B-Tree indexes for fast transaction history lookups for users.
*   **`merchant_settlements(status, created_at)`:** Composite index to allow the Settlement Cron to quickly fetch the oldest `PENDING` settlements.

## Partitioning Strategy
Tables like `transactions` and `ledger_entries` will grow massive. To manage this:
*   We use PostgreSQL Native Declarative Partitioning by `RANGE (created_at)`.
*   Partitions are created **monthly** (e.g., `transactions_2026_09`, `transactions_2026_10`).
*   This allows fast archiving and dropping of old data according to RBI's 2-year hot data retention policy, without expensive `DELETE` operations.

## Data Definition Language (DDL) Scripts
The explicit `CREATE TABLE` and constraint SQL scripts are organized in the `/schemas/ddl/` directory, following the sequence:
1. `001-users.sql`
2. `002-accounts.sql`
3. `003-transactions.sql`
4. `004-ledger_entries.sql`
5. `005-transaction_events.sql`
6. `006-fraud_rules.sql`
7. `007-merchant_settlements.sql`
8. `008-notification_log.sql`
