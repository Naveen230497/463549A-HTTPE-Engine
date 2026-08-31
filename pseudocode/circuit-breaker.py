import time
from enum import Enum
import functools

class State(Enum):
    CLOSED = "CLOSED"     # Normal operation
    OPEN = "OPEN"         # Failing, short-circuiting requests
    HALF_OPEN = "HALF_OPEN" # Testing recovery

class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout_sec=15):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        
        self.state = State.CLOSED
        self.failures = 0
        self.last_failure_time = None

    def call(self, func, fallback_func, *args, **kwargs):
        if self.state == State.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout_sec:
                # Time to test if the service is back up
                self.state = State.HALF_OPEN
            else:
                # Still open, short-circuit and run fallback immediately
                return fallback_func(*args, **kwargs)
                
        try:
            # Attempt the actual call
            result = func(*args, **kwargs)
            
            # If we were half-open and it succeeded, the service is healthy again
            if self.state == State.HALF_OPEN:
                self._reset()
                
            return result
            
        except Exception as e:
            # The call failed (e.g., Timeout, ConnectionReset)
            self.failures += 1
            self.last_failure_time = time.time()
            
            if self.failures >= self.failure_threshold:
                self.state = State.OPEN
                
            # Execute fallback logic
            return fallback_func(*args, **kwargs)

    def _reset(self):
        self.state = State.CLOSED
        self.failures = 0
        self.last_failure_time = None

# Example Usage
def fraud_evaluation_rpc(transaction_data):
    # Simulates a gRPC call that might timeout > 15ms
    raise TimeoutError("Fraud service took too long")

def fraud_fallback(transaction_data):
    # Fallback: Allow transaction but flag for manual review
    return {"status": "ALLOWED", "flag": "MANUAL_REVIEW_REQUIRED"}

cb_fraud = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=15)

def process_payment(data):
    # This will quickly fallback without waiting for a timeout if CB is OPEN
    fraud_result = cb_fraud.call(fraud_evaluation_rpc, fraud_fallback, data)
    return fraud_result
