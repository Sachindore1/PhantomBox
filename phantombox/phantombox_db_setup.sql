DROP DATABASE IF EXISTS phantombox_db;
CREATE DATABASE phantombox_db;
USE phantombox_db;

-- 1. Users Table (Must use VARCHAR(36) for both sides of foreign keys)
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role ENUM('Admin', 'User') DEFAULT 'User',
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NULL,
    failed_login_attempts INT DEFAULT 0,
    locked_until BIGINT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. User Sessions Table
CREATE TABLE user_sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    is_active TINYINT(1) DEFAULT 1,
    created_at BIGINT,
    expires_at BIGINT,
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. File Registry Table
CREATE TABLE file_registry (
    file_id VARCHAR(255) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL,
    original_filename VARCHAR(255),
    file_hash VARCHAR(64),
    fragment_count INT DEFAULT 3,
    file_size BIGINT DEFAULT 0,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_file_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Audit Ledger Table
CREATE TABLE audit_ledger (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action_type VARCHAR(50),
    user_id VARCHAR(36),
    file_id VARCHAR(255),
    details TEXT,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;