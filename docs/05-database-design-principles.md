# Database Design Principles

This document explains database design principles, normalization, indexing strategies, and transaction design used in Traffic Manager.

## Table of Contents

1. [Relational Database Fundamentals](#relational-database-fundamentals)
2. [Normalization](#normalization)
3. [Denormalization](#denormalization)
4. [Indexing Strategies](#indexing-strategies)
5. [Foreign Keys and Referential Integrity](#foreign-keys-and-referential-integrity)
6. [Transaction Design](#transaction-design)
7. [ACID Properties](#acid-properties)
8. [Isolation Levels](#isolation-levels)
9. [Query Optimization](#query-optimization)
10. [Traffic Manager's Schema Design](#traffic-managers-schema-design)

---

## Relational Database Fundamentals

### What is a Relational Database?

**Relational database** stores data in tables (relations) with relationships between them.

### Key Concepts

1. **Table**: Collection of rows (records)
2. **Row**: Single record (tuple)
3. **Column**: Attribute (field)
4. **Primary Key**: Unique identifier for row
5. **Foreign Key**: Reference to another table
6. **Relationship**: Link between tables

### Example: Traffic Manager Schema

```
tenants (1) ──< (many) services (1) ──< (many) environments (1) ──< (many) endpoints
```

**Relationships:**
- One tenant has many services
- One service has many environments
- One environment has many endpoints

---

## Normalization

**Normalization** is the process of organizing data to reduce redundancy and improve integrity.

### Normal Forms

#### 1NF (First Normal Form)

**Rule**: Each column contains atomic (indivisible) values.

**Violation:**
```
services
  id | tenant_id | name | environments
  1  | 1         | payments | prod,staging,dev
```

**Fixed:**
```
services
  id | tenant_id | name
  1  | 1         | payments

environments
  id | service_id | name
  1  | 1          | prod
  2  | 1          | staging
  3  | 1          | dev
```

#### 2NF (Second Normal Form)

**Rule**: 1NF + no partial dependencies (all non-key columns depend on full primary key).

**Violation:**
```
endpoints
  id | environment_id | version | url | environment_name
  1  | 1              | v1      | ... | prod
```

`environment_name` depends only on `environment_id`, not full key.

**Fixed:**
```
endpoints
  id | environment_id | version | url

environments
  id | name
  1  | prod
```

#### 3NF (Third Normal Form)

**Rule**: 2NF + no transitive dependencies (non-key columns don't depend on other non-key columns).

**Violation:**
```
services
  id | tenant_id | tenant_name | name
  1  | 1         | team-a      | payments
```

`tenant_name` depends on `tenant_id`, not on `id`.

**Fixed:**
```
services
  id | tenant_id | name

tenants
  id | name
  1  | team-a
```

### Benefits of Normalization

- ✅ **Reduces redundancy**: Data stored once
- ✅ **Prevents anomalies**: Update/delete anomalies avoided
- ✅ **Saves space**: Less duplicate data
- ✅ **Easier maintenance**: Update in one place

### Drawbacks

- ❌ **More joins**: Need to join tables
- ❌ **Slower queries**: More complex queries
- ❌ **More tables**: Schema is more complex

### Traffic Manager's Normalization

**Fully normalized** (3NF):
- Each concept in separate table
- No redundancy
- Foreign keys maintain relationships

---

## Denormalization

**Denormalization** is intentionally adding redundancy to improve performance.

### When to Denormalize

- **Read-heavy workloads**: Joins are expensive
- **Performance critical**: Need fast queries
- **Acceptable trade-off**: Redundancy OK for speed

### Example: Denormalized Route Table

```sql
-- Denormalized (all in one table)
CREATE TABLE routes (
  id SERIAL PRIMARY KEY,
  tenant_name TEXT,
  service_name TEXT,
  env_name TEXT,
  version TEXT,
  url TEXT,
  is_active BOOLEAN
);
```

**Pros:**
- ✅ Fast reads (no joins)
- ✅ Simple queries

**Cons:**
- ❌ Data redundancy
- ❌ Update anomalies (must update multiple rows)
- ❌ More storage

### Traffic Manager's Approach

**Normalized** (not denormalized):
- Performance acceptable with proper indexes
- Data integrity more important
- Can denormalize later if needed (materialized views)

---

## Indexing Strategies

**Index** = data structure that speeds up queries (like book index).

### Types of Indexes

#### 1. B-Tree Index (Default)

**Structure**: Balanced tree, sorted data.

**Use case**: Equality and range queries.

```sql
CREATE INDEX idx_tenants_name ON tenants(name);

-- Fast: Uses index
SELECT * FROM tenants WHERE name = 'team-a';

-- Fast: Uses index
SELECT * FROM tenants WHERE name > 'team-a';
```

#### 2. Hash Index

**Structure**: Hash table.

**Use case**: Only equality queries.

```sql
CREATE INDEX idx_hash ON table USING HASH(column);

-- Fast: Uses hash index
SELECT * FROM table WHERE column = 'value';

-- Slow: Can't use hash index
SELECT * FROM table WHERE column > 'value';
```

#### 3. Composite Index

**Structure**: Index on multiple columns.

**Use case**: Queries filtering on multiple columns.

```sql
CREATE INDEX idx_composite ON services(tenant_id, name);

-- Fast: Uses composite index
SELECT * FROM services WHERE tenant_id = 1 AND name = 'payments';

-- Fast: Uses index (leftmost prefix)
SELECT * FROM services WHERE tenant_id = 1;

-- Slow: Can't use index (name not leftmost)
SELECT * FROM services WHERE name = 'payments';
```

### Index Design Principles

1. **Index frequently queried columns**
2. **Index foreign keys** (for joins)
3. **Index WHERE clause columns**
4. **Index ORDER BY columns** (if needed)
5. **Don't over-index** (slows writes)

### Traffic Manager's Indexes

```sql
-- Lookup by name (frequent)
CREATE INDEX idx_tenants_name ON tenants(name);

-- Join optimization
CREATE INDEX idx_services_tenant ON services(tenant_id);
CREATE INDEX idx_env_service ON environments(service_id);

-- Query optimization (active routes)
CREATE INDEX idx_endpoints_env_active ON endpoints(environment_id, is_active);
```

**Why these?**
- Name lookups are frequent
- Foreign keys used in joins
- Active filter used in read path

---

## Foreign Keys and Referential Integrity

**Foreign key** = column referencing primary key in another table.

### Benefits

- ✅ **Referential integrity**: Can't reference non-existent row
- ✅ **Cascading deletes**: Can delete parent and children
- ✅ **Data consistency**: Relationships always valid

### Example

```sql
CREATE TABLE services (
  id SERIAL PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL
);
```

**What this enforces:**
- `tenant_id` must exist in `tenants` table
- Can't delete tenant if services reference it (unless CASCADE)
- Database maintains consistency

### Cascade Options

```sql
-- ON DELETE CASCADE: Delete children when parent deleted
REFERENCES tenants(id) ON DELETE CASCADE

-- ON DELETE RESTRICT: Prevent delete if children exist (default)
REFERENCES tenants(id) ON DELETE RESTRICT

-- ON DELETE SET NULL: Set foreign key to NULL
REFERENCES tenants(id) ON DELETE SET NULL
```

### Traffic Manager's Foreign Keys

**All use RESTRICT** (default):
- Prevents accidental data loss
- Must explicitly handle deletions
- Safe for production

---

## Transaction Design

**Transaction** = sequence of operations that execute as a single unit.

### Transaction Properties (ACID)

See [ACID Properties](#acid-properties) section below.

### Transaction Patterns

#### 1. Single-Statement Transaction

```sql
-- Automatically a transaction
INSERT INTO tenants (name) VALUES ('team-a');
```

#### 2. Multi-Statement Transaction

```sql
BEGIN;
  INSERT INTO tenants (name) VALUES ('team-a');
  INSERT INTO services (tenant_id, name) VALUES (1, 'payments');
COMMIT;
```

#### 3. Transaction with Error Handling

```sql
BEGIN;
  INSERT INTO tenants (name) VALUES ('team-a');
  INSERT INTO services (tenant_id, name) VALUES (1, 'payments');
  -- If error occurs, ROLLBACK happens automatically
COMMIT;
```

### Traffic Manager's Transactions

**All writes use transactions**:
- Create route: Multiple inserts in one transaction
- Activate/deactivate: Update in transaction
- Ensures atomicity and consistency

---

## ACID Properties

### Atomicity

**All or nothing**: Transaction either fully completes or fully fails.

```sql
BEGIN;
  UPDATE accounts SET balance = balance - 100 WHERE id = 1;
  UPDATE accounts SET balance = balance + 100 WHERE id = 2;
  -- If second update fails, first is rolled back
COMMIT;
```

### Consistency

**Valid state**: Database remains in valid state (constraints satisfied).

```sql
-- Constraint: balance >= 0
BEGIN;
  UPDATE accounts SET balance = -50 WHERE id = 1;  -- Fails!
ROLLBACK;
```

### Isolation

**Concurrent transactions don't interfere**.

```sql
-- Transaction 1
BEGIN;
  SELECT balance FROM accounts WHERE id = 1;  -- Reads 100
  -- Transaction 2 updates balance to 200
  UPDATE accounts SET balance = balance - 50 WHERE id = 1;
COMMIT;  -- Final balance: 50 (not 150)
```

### Durability

**Committed changes survive failures**.

```sql
COMMIT;  -- Data written to disk, survives crash
```

---

## Isolation Levels

**Isolation level** = how transactions see each other's changes.

### Levels (from weakest to strongest)

#### 1. Read Uncommitted

**See uncommitted changes** (dirty reads).

```sql
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
```

**Problem**: May see data that gets rolled back.

#### 2. Read Committed (PostgreSQL default)

**See only committed changes**.

```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

**Problem**: Non-repeatable reads (same query, different results).

#### 3. Repeatable Read

**Same query always returns same results**.

```sql
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
```

**Problem**: Phantom reads (new rows appear).

#### 4. Serializable

**Highest isolation**: Transactions appear to execute serially.

```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

**Problem**: May fail with serialization errors (retry needed).

### Traffic Manager's Isolation

**Read Committed** (PostgreSQL default):
- Good balance of correctness and performance
- Sufficient for our use case
- No need for higher isolation

---

## Query Optimization

### Query Execution Plan

**Plan** = how database executes query.

```sql
EXPLAIN SELECT * FROM endpoints WHERE environment_id = 1;
```

**Output:**
```
Seq Scan on endpoints  (cost=0.00..100.00 rows=10)
  Filter: (environment_id = 1)
```

### Optimization Techniques

1. **Use indexes**: Create indexes on filtered columns
2. **Avoid SELECT ***: Select only needed columns
3. **Use LIMIT**: Limit result set
4. **Join optimization**: Index foreign keys
5. **Avoid functions in WHERE**: Can't use indexes

### Traffic Manager's Queries

**Optimized read path query**:
```sql
SELECT e.url
FROM tenants t
JOIN services s ON s.tenant_id = t.id
JOIN environments env ON env.service_id = s.id
JOIN endpoints e ON e.environment_id = env.id
WHERE t.name = $1
  AND s.name = $2
  AND env.name = $3
  AND e.version = $4
  AND e.is_active = true
LIMIT 1;
```

**Why optimized:**
- Uses indexes on name columns
- Uses composite index on (environment_id, is_active)
- LIMIT 1 stops after first match
- Joins use indexed foreign keys

---

## Traffic Manager's Schema Design

### Design Decisions

1. **Normalized**: 3NF (no redundancy)
2. **Indexed**: Frequently queried columns
3. **Foreign keys**: Referential integrity
4. **Unique constraints**: Prevent duplicates (idempotency)
5. **Soft deletion**: `is_active` flag (not hard delete)

### Schema Structure

```
tenants (id, name)
  └─ services (id, tenant_id, name)
      └─ environments (id, service_id, name)
          └─ endpoints (id, environment_id, version, url, is_active)
```

### Why This Design?

1. **Flexibility**: Easy to add new tenants/services
2. **Integrity**: Foreign keys ensure consistency
3. **Performance**: Indexes optimize queries
4. **Idempotency**: Unique constraints prevent duplicates
5. **Audit**: Soft deletion preserves history

### Trade-offs

- ✅ **Normalized**: Data integrity, no redundancy
- ✅ **Indexed**: Fast queries
- ❌ **Joins required**: More complex queries
- ❌ **More tables**: More complex schema

**Acceptable trade-off**: Performance is good with proper indexes.

---

## Key Takeaways

1. **Normalization** = reduce redundancy, improve integrity
2. **Denormalization** = add redundancy for performance
3. **Indexes** = speed up queries (but slow writes)
4. **Foreign keys** = maintain referential integrity
5. **Transactions** = atomic, consistent operations
6. **ACID** = Atomicity, Consistency, Isolation, Durability
7. **Isolation levels** = how transactions see each other
8. **Query optimization** = indexes, LIMIT, selective columns

Understanding database design helps you:
- Design efficient schemas
- Optimize queries
- Maintain data integrity
- Balance normalization and performance
