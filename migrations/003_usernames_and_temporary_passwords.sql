ALTER TABLE users ADD COLUMN username TEXT CHECK(username IS NULL OR (length(username) BETWEEN 3 AND 32 AND username=lower(username)));
ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN temporary_password_expires_at BIGINT;
ALTER TABLE member_invitations ADD COLUMN kind TEXT NOT NULL DEFAULT 'activation' CHECK(kind IN ('activation','temporary_password'));
CREATE UNIQUE INDEX users_username_unique ON users(lower(username));
