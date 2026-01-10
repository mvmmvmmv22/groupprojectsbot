CREATE DATABASE IF NOT EXISTS project_management;

\c project_management;

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    creator_id BIGINT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    deadline TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    next_notificaton TIMESTAMP WITHOUT TIME ZONE,
    last_notification_sent TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL,
    user_id BIGINT NOT NULL,
    joined_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invites (
    key VARCHAR NOT NULL,
    active BOOLEAN NOT NULL,
    answer BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_settings (
    user_id BIGINT NOT NULL
    enable_reminders BOOLEAN DEFAULT True,
    reminder_hours INTEGER DEFAULT '{24,6,1}'::integer[],
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
