import time
from exceptions import InsufficientFundsError, DatabaseError, OCCMaxRetriesExceeded

class AccountService:
    def __init__(self, db_pool):
        self.db = db_pool
        self.MAX_RETRIES = 5
        self.BASE_BACKOFF_MS = 10

    def process_debit(self, account_id: str, amount: float) -> dict:
        """
        Executes a lock-free debit using Optimistic Concurrency Control.
        Guarantees protection against write-skew and double-spending.
        """
        retries = 0
        
        while retries < self.MAX_RETRIES:
            # 1. Read current state (No locks held)
            account = self.db.query(
                "SELECT available_balance, version FROM accounts WHERE account_id = %s", 
                [account_id]
            )
            
            if not account:
                raise ValueError("Account not found")
                
            current_balance = account['available_balance']
            current_version = account['version']
            
            # 2. Business Logic Validation
            if current_balance < amount:
                raise InsufficientFundsError(f"Required: {amount}, Available: {current_balance}")
                
            new_balance = current_balance - amount
            new_version = current_version + 1
            
            # 3. Atomic Compare-and-Swap (OCC Update)
            rows_updated = self.db.execute("""
                UPDATE accounts 
                SET available_balance = %s, version = %s, updated_at = NOW()
                WHERE account_id = %s AND version = %s
            """, [new_balance, new_version, account_id, current_version])
            
            # 4. Check for concurrent modification
            if rows_updated == 1:
                # Success! No other transaction modified this row.
                return {"status": "SUCCESS", "new_balance": new_balance}
            else:
                # Conflict detected. Another transaction updated the row first.
                # The WHERE version = current_version clause failed.
                retries += 1
                
                # Apply exponential backoff with jitter to prevent thundering herd
                backoff_time = (self.BASE_BACKOFF_MS * (2 ** retries))
                time.sleep(backoff_time / 1000.0)
                
        # If we exit the loop, contention is too high
        raise OCCMaxRetriesExceeded("Failed to process transaction due to high contention.")
