# MySQL Setup Guide

This guide explains how to set up and use MySQL instead of SQLite for the Claude Task Automation Server.

## Why MySQL?

MySQL offers several advantages over SQLite for this application:

- **Better Concurrency**: Handles multiple concurrent requests better
- **Production Ready**: Suitable for production deployments
- **Remote Access**: Can connect from multiple servers
- **Better Performance**: Optimized for server workloads
- **Transaction Support**: Better ACID compliance
- **Scalability**: Can handle larger datasets

## Prerequisites

- MySQL Server installed and running
- MySQL credentials (default: root/sitebuilder)
- Python dependencies installed

## Quick Setup

### 1. Install MySQL Dependencies

```bash
pip install pymysql cryptography
```

Or if using the full requirements:

```bash
pip install -r requirements.txt
```

### 2. Configure Database Connection

Edit `.env` file:

```bash
# Use MySQL instead of SQLite
DATABASE_URL=mysql+pymysql://root:sitebuilder@localhost/claudesys
```

### 3. Create Database and Tables

Run the setup script:

```bash
python setup_mysql.py
```

This will:
- Connect to MySQL server
- Create `claudesys` database
- Initialize all tables
- Verify the setup

### 4. Start the Server

```bash
python -m app.main
```

## Manual Setup

If you prefer to set up manually:

### 1. Create Database

```sql
-- Connect to MySQL
mysql -u root -p

-- Create database
CREATE DATABASE IF NOT EXISTS claudesys
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- Verify
SHOW DATABASES;
USE claudesys;
```

### 2. Initialize Tables

```python
# In Python shell or script
from app.database import init_db
init_db()
```

Or start the server (it will auto-initialize):

```bash
python -m app.main
```

## Database Schema

The system creates the following tables:

### sessions
- `id` (VARCHAR, Primary Key)
- `project_path` (VARCHAR)
- `created_at` (DATETIME)
- `updated_at` (DATETIME)

### tasks
- `id` (VARCHAR, Primary Key)
- `session_id` (VARCHAR, Foreign Key → sessions.id)
- `description` (TEXT)
- `status` (ENUM)
- `summary` (TEXT)
- `error_message` (TEXT)
- `created_at` (DATETIME)
- `updated_at` (DATETIME)
- `completed_at` (DATETIME)

### test_cases
- `id` (VARCHAR, Primary Key)
- `task_id` (VARCHAR, Foreign Key → tasks.id)
- `name` (VARCHAR)
- `description` (TEXT)
- `test_code` (TEXT)
- `test_type` (ENUM: generated, regression)
- `status` (ENUM: pending, passed, failed)
- `output` (TEXT)
- `created_at` (DATETIME)
- `updated_at` (DATETIME)

### claude_interactions
- `id` (VARCHAR, Primary Key)
- `task_id` (VARCHAR, Foreign Key → tasks.id)
- `interaction_type` (ENUM: user_request, claude_response, simulated_human)
- `content` (TEXT)
- `created_at` (DATETIME)

## Connection String Format

```
mysql+pymysql://[user]:[password]@[host]:[port]/[database]
```

### Examples

**Local MySQL (default port 3306):**
```
DATABASE_URL=mysql+pymysql://root:sitebuilder@localhost/claudesys
```

**Custom Port:**
```
DATABASE_URL=mysql+pymysql://root:sitebuilder@localhost:3307/claudesys
```

**Remote MySQL:**
```
DATABASE_URL=mysql+pymysql://user:pass@mysql.example.com/claudesys
```

**With SSL:**
```
DATABASE_URL=mysql+pymysql://user:pass@mysql.example.com/claudesys?ssl_ca=/path/to/ca.pem
```

## Database Configuration

The system automatically configures MySQL with optimal settings:

```python
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,              # Max 10 connections
    pool_recycle=3600,         # Recycle connections every hour
    pool_pre_ping=True,        # Verify connections before use
    echo=False,                # Set to True for SQL debugging
)
```

### Connection Pool

- **Pool Size**: 10 concurrent connections
- **Pool Recycle**: Connections recycled every hour
- **Pre-Ping**: Verifies connection before use (prevents stale connections)

### Adjusting Pool Size

For high-traffic deployments, increase pool size:

```python
# In app/database.py
pool_size=20,  # Allow 20 concurrent connections
max_overflow=10,  # Allow 10 additional connections when needed
```

## Troubleshooting

### Connection Refused

```
Error: Can't connect to MySQL server on 'localhost'
```

**Solutions:**
1. Verify MySQL is running: `sudo systemctl status mysql`
2. Check MySQL port: `mysql -u root -p -e "SHOW VARIABLES LIKE 'port';"`
3. Verify credentials: `mysql -u root -p`

### Access Denied

```
Error: Access denied for user 'root'@'localhost'
```

**Solutions:**
1. Verify password: `mysql -u root -p`
2. Check user permissions:
   ```sql
   SELECT User, Host FROM mysql.user;
   SHOW GRANTS FOR 'root'@'localhost';
   ```
3. Create new user if needed:
   ```sql
   CREATE USER 'claudeuser'@'localhost' IDENTIFIED BY 'password';
   GRANT ALL PRIVILEGES ON claudesys.* TO 'claudeuser'@'localhost';
   FLUSH PRIVILEGES;
   ```

### Database Not Found

```
Error: Unknown database 'claudesys'
```

**Solution:**
Run the setup script:
```bash
python setup_mysql.py
```

Or create manually:
```sql
CREATE DATABASE claudesys;
```

### Table Already Exists

```
Error: Table 'sessions' already exists
```

**This is normal.** SQLAlchemy's `create_all()` is idempotent - it won't recreate existing tables.

To reset the database:
```sql
DROP DATABASE claudesys;
CREATE DATABASE claudesys;
```

Then run `python setup_mysql.py` again.

### Character Set Issues

```
Error: Incorrect string value
```

**Solution:**
Ensure database uses UTF-8:
```sql
ALTER DATABASE claudesys CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## Performance Tuning

### Indexes

The system automatically creates indexes via SQLAlchemy. To verify:

```sql
USE claudesys;
SHOW INDEX FROM tasks;
SHOW INDEX FROM sessions;
```

### Query Optimization

Monitor slow queries:

```sql
-- Enable slow query log
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;

-- View slow queries
SELECT * FROM mysql.slow_log;
```

### Connection Monitoring

Check active connections:

```sql
SHOW PROCESSLIST;
SHOW STATUS LIKE 'Threads_connected';
```

## Backup and Restore

### Backup Database

```bash
# Full backup
mysqldump -u root -p claudesys > claudesys_backup.sql

# Backup with timestamp
mysqldump -u root -p claudesys > claudesys_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
mysqldump -u root -p claudesys | gzip > claudesys_backup.sql.gz
```

### Restore Database

```bash
# Restore from backup
mysql -u root -p claudesys < claudesys_backup.sql

# Restore compressed backup
gunzip < claudesys_backup.sql.gz | mysql -u root -p claudesys
```

### Automated Backups

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * mysqldump -u root -psitebuilder claudesys | gzip > /backups/claudesys_$(date +\%Y\%m\%d).sql.gz
```

## Migration from SQLite

To migrate from SQLite to MySQL:

### 1. Export SQLite Data

```bash
sqlite3 tasks.db .dump > sqlite_dump.sql
```

### 2. Convert SQL Syntax

SQLite and MySQL have some differences. You may need to:
- Remove `AUTOINCREMENT` keywords
- Convert data types
- Fix quote characters

### 3. Import to MySQL

```bash
mysql -u root -p claudesys < converted_dump.sql
```

### Alternative: Use Python Script

```python
# migrate_sqlite_to_mysql.py
from app.database import SessionLocal
from app.models import Session, Task, TestCase, ClaudeInteraction
import sqlite3

# Export from SQLite
sqlite_conn = sqlite3.connect('tasks.db')
# ... fetch data ...

# Import to MySQL (update DATABASE_URL first)
db = SessionLocal()
# ... insert data ...
db.commit()
```

## Security Best Practices

### 1. Don't Use Root in Production

Create a dedicated user:

```sql
CREATE USER 'claudeapp'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON claudesys.* TO 'claudeapp'@'localhost';
FLUSH PRIVILEGES;
```

### 2. Use Strong Passwords

```bash
# Generate strong password
openssl rand -base64 32
```

### 3. Restrict Access

```sql
-- Only allow localhost
CREATE USER 'claudeapp'@'localhost' IDENTIFIED BY 'password';

-- Allow specific IP
CREATE USER 'claudeapp'@'192.168.1.100' IDENTIFIED BY 'password';
```

### 4. Use Environment Variables

Never commit passwords to git:

```bash
# .env (add to .gitignore)
DATABASE_URL=mysql+pymysql://claudeapp:${DB_PASSWORD}@localhost/claudesys
```

### 5. Enable SSL

```sql
-- Require SSL for user
ALTER USER 'claudeapp'@'localhost' REQUIRE SSL;
```

## Monitoring

### Check Database Size

```sql
SELECT
    table_schema AS 'Database',
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Size (MB)'
FROM information_schema.tables
WHERE table_schema = 'claudesys'
GROUP BY table_schema;
```

### Table Statistics

```sql
SELECT
    table_name AS 'Table',
    table_rows AS 'Rows',
    ROUND(data_length / 1024 / 1024, 2) AS 'Data (MB)',
    ROUND(index_length / 1024 / 1024, 2) AS 'Index (MB)'
FROM information_schema.tables
WHERE table_schema = 'claudesys';
```

## Development vs Production

### Development (SQLite)

```bash
# .env.development
DATABASE_URL=sqlite:///./tasks.db
```

### Production (MySQL)

```bash
# .env.production
DATABASE_URL=mysql+pymysql://claudeapp:${DB_PASSWORD}@mysql-server/claudesys
```

Switch between environments:

```bash
# Development
cp .env.development .env
python -m app.main

# Production
cp .env.production .env
python -m app.main
```

## Conclusion

MySQL provides a robust, production-ready database solution for the Claude Task Automation Server. Follow this guide for setup, and refer to the troubleshooting section for common issues.

For questions or issues, check the MySQL documentation or review the server logs.
