# Scripts Directory

This directory contains utility scripts for the Traffic Manager application.

## Available Scripts

### 1. `populate_db.py`

Populates the database with sample route data for testing and demonstration.

**Usage:**
```bash
python scripts/populate_db.py
```

**What it does:**
- Creates sample tenants (team-a, team-b)
- Creates sample services (payments, orders, users, analytics)
- Creates sample environments (prod, staging, dev)
- Creates sample routes with different versions

**Sample data created:**
- team-a/payments/prod/v1, v2
- team-a/payments/staging/v2
- team-a/payments/dev/v3
- team-a/orders/prod/v1, v2
- team-b/users/prod/v1, v2
- team-b/users/staging/v2
- team-b/analytics/prod/v1

### 2. `check_datastores.sh`

Quick health check script for all datastores (PostgreSQL, Redis, Kafka).

**Usage:**
```bash
./scripts/check_datastores.sh
```

**What it checks:**
- PostgreSQL connectivity and endpoint count
- Redis connectivity and cache key count
- Kafka connectivity and topic count

### 3. `check_datastores.md`

Detailed guide on how to manually check each datastore.

**See:** `scripts/check_datastores.md` for complete instructions.

### 4. `run_consumer.py`

Runs one Kafka consumer for a specific use case.

**Usage:**
```bash
python scripts/run_consumer.py cache_invalidation
python scripts/run_consumer.py cache_warming
python scripts/run_consumer.py audit_log
```

---

## Quick Start

### 1. Start Datastores

```bash
cd datastore
docker-compose up -d
```

### 2. Initialize Database Schema

```bash
cd datastore/db
./init_db.sh
```

### 3. Populate Sample Data

```bash
cd ../..
python scripts/populate_db.py
```

### 4. Check Datastores

```bash
./scripts/check_datastores.sh
```

### 5. Start Application

```bash
python src/main.py
```

---

## Troubleshooting

### Import Errors

If you get import errors when running scripts, make sure you're running from the project root:

```bash
# Correct
cd /path/to/traffic-manager
python scripts/populate_db.py

# Wrong
cd /path/to/traffic-manager/scripts
python populate_db.py
```

### Database Connection Errors

Make sure PostgreSQL is running:

```bash
docker ps | grep postgres
```

If not running, start it:

```bash
cd datastore
docker-compose up -d postgresql
```

### Permission Errors

Make scripts executable:

```bash
chmod +x scripts/*.sh
chmod +x scripts/*.py
```
