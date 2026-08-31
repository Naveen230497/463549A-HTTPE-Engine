import json

class RedisClientMock:
    def set(self, key, value, nx, ex): pass
    def get(self, key): pass

redis = RedisClientMock()

class IdempotencyMiddleware:
    """
    Middleware that runs at the API Gateway or Payment Service boundary.
    Ensures that a client retrying a POST request does not trigger duplicate processing.
    """
    def __init__(self, ttl_seconds=86400): # 24 hours
        self.ttl = ttl_seconds

    def handle_request(self, request, next_handler):
        idempotency_key = request.headers.get("X-Idempotency-Key")
        
        if not idempotency_key:
            return {"status": 400, "body": "X-Idempotency-Key header is required"}
            
        redis_key = f"idempotency:{idempotency_key}"
        
        # 1. Check if we already processed this
        cached_response = redis.get(redis_key)
        if cached_response:
            # We already processed this exact request. Return the saved response.
            return json.loads(cached_response)
            
        # 2. Try to acquire a lock to prevent concurrent identical requests
        # NX=True means Set ONLY if it does not exist. 
        # Prevents race condition if client sends 2 identical requests at the exact same millisecond.
        lock_acquired = redis.set(f"{redis_key}:lock", "locked", nx=True, ex=10)
        
        if not lock_acquired:
            # Another request with this key is currently being processed right now.
            return {"status": 409, "body": "Concurrent request processing. Please try again later."}
            
        try:
            # 3. Process the actual business logic (Saga, Database updates)
            actual_response = next_handler(request)
            
            # 4. Save the successful response so future retries get it
            # We only cache successful or deterministic terminal states (e.g., 200 OK, 400 Bad Request)
            # We do NOT cache 500 Internal Server Errors, because we want the client to retry those.
            if actual_response['status'] < 500:
                redis.set(redis_key, json.dumps(actual_response), nx=False, ex=self.ttl)
                
            return actual_response
            
        finally:
            # Always release the processing lock
            redis.delete(f"{redis_key}:lock")
