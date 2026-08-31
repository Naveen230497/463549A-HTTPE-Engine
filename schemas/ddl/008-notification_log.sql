CREATE TABLE notification_log (log_id UUID PRIMARY KEY, user_id UUID REFERENCES users(user_id) NOT NULL, message TEXT NOT NULL, status VARCHAR(20) NOT NULL, created_at TIMESTAMPTZ NOT NULL);
