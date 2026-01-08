CREATE DATABASE IF NOT EXISTS project_management;

\c project_management;

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS projects (
    project_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    creator_id BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'active',
    CONSTRAINT fk_creator
        FOREIGN KEY (creator_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_projects_creator ON projects (creator_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_created ON projects (created_at);

CREATE TABLE IF NOT EXISTS project_members (
    project_id INT NOT NULL,
    user_id BIGINT NOT NULL,
    role VARCHAR(100) DEFAULT 'member',
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    PRIMARY KEY (project_id, user_id),

    CONSTRAINT fk_project
        FOREIGN KEY (project_id)
        REFERENCES projects (project_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_user
        FOREIGN KEY (user_id)
        REFERENCES users (user_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_project_members_user ON project_members (user_id);
CREATE INDEX IF NOT EXISTS idx_project_members_role ON project_members (role);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER trigger_update_projects
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
