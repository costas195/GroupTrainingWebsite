ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0;
CREATE TABLE login_attempts(bucket TEXT PRIMARY KEY,window_start BIGINT NOT NULL,attempts INTEGER NOT NULL);
CREATE INDEX login_attempts_window ON login_attempts(window_start);
