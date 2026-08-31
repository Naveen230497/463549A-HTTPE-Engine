import http from 'k6/http';
import { check, sleep } from 'k6';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

export const options = {
    scenarios: {
        target_load: {
            executor: 'ramping-arrival-rate',
            startRate: 1000,
            timeUnit: '1s',
            preAllocatedVUs: 2000,
            maxVUs: 15000,
            stages: [
                { target: 12000, duration: '5m' },   // Ramp up to 12k TPS
                { target: 12000, duration: '60m' },  // Sustain 12k TPS
                { target: 0, duration: '5m' },       // Cool down
            ],
        },
    },
    thresholds: {
        http_req_duration: ['p(99)<100'], // 99% of requests must complete below 100ms
        http_req_failed: ['rate<0.0001'], // Error rate must be less than 0.01%
    },
};

export default function () {
    const url = 'https://api.payscale.local/v1/payments/p2p';
    
    // Generate unique idempotency key for every request
    const idempotencyKey = uuidv4();
    
    const payload = JSON.stringify({
        sender_account_id: uuidv4(), // In reality, fetch from a pre-generated CSV
        receiver_account_id: uuidv4(),
        amount: Math.floor(Math.random() * 1000) + 1,
        currency: "INR"
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
            'X-Idempotency-Key': idempotencyKey,
            'Authorization': 'Bearer SIMULATED_TOKEN'
        },
    };

    const res = http.post(url, payload, params);

    check(res, {
        'is status 202': (r) => r.status === 202,
        'has transaction_id': (r) => JSON.parse(r.body).transaction_id !== undefined,
    });
}
