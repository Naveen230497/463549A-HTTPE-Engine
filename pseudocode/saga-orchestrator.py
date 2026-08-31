from temporalio import workflow
from datetime import timedelta

# Define the workflow orchestrator using Temporal.io python SDK concepts
@workflow.defn
class P2PPaymentSaga:
    
    @workflow.run
    async def run(self, transaction_id: str, sender_id: str, receiver_id: str, amount: float):
        # State tracking for compensation
        debit_successful = False
        
        try:
            # STEP 1: Debit Sender (Execute Activity)
            # Uses OCC under the hood. Temporal handles automatic retries on network failures.
            await workflow.execute_activity(
                "DebitAccountActivity",
                args=[sender_id, amount, transaction_id],
                start_to_close_timeout=timedelta(seconds=5)
            )
            debit_successful = True
            
            # STEP 2: Credit Receiver (Execute Activity)
            await workflow.execute_activity(
                "CreditAccountActivity",
                args=[receiver_id, amount, transaction_id],
                start_to_close_timeout=timedelta(seconds=5)
            )
            
            # STEP 3: Write Ledger Entries
            await workflow.execute_activity(
                "WriteLedgerActivity",
                args=[transaction_id, sender_id, receiver_id, amount],
                start_to_close_timeout=timedelta(seconds=5)
            )
            
            # STEP 4: Mark Complete & Trigger async downstream events
            await workflow.execute_activity(
                "PublishCompletionEventActivity",
                args=[transaction_id, "SUCCESS"],
                start_to_close_timeout=timedelta(seconds=2)
            )
            
            return "COMPLETED"
            
        except Exception as e:
            # SAGA COMPENSATION LOGIC (Rollback)
            workflow.logger.error(f"Saga failed at transaction {transaction_id}: {str(e)}")
            
            if debit_successful:
                # If we debited the sender but failed later, we MUST refund the sender.
                try:
                    await workflow.execute_activity(
                        "CompensateDebitActivity", # essentially a credit back
                        args=[sender_id, amount, transaction_id],
                        start_to_close_timeout=timedelta(seconds=10),
                        retry_policy={"maximum_attempts": 100} # Critical: must eventually succeed
                    )
                except Exception as comp_e:
                    # Extreme edge case: compensation fails completely.
                    # Requires manual operator intervention / DLQ alerting.
                    workflow.logger.critical(f"COMPENSATION FAILED for {transaction_id}: {str(comp_e)}")
                    
            # Mark transaction as failed in the DB
            await workflow.execute_activity(
                "MarkTransactionFailedActivity",
                args=[transaction_id, str(e)],
                start_to_close_timeout=timedelta(seconds=5)
            )
            
            return "FAILED"
