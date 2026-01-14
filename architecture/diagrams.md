# Traffic Manager - Architecture Diagrams

This file contains Mermaid diagrams visualizing the Traffic Manager architecture.

## 1. System Architecture Overview

```mermaid
graph TB
    subgraph "Client Layer"
        Client[Client Application]
    end
    
    subgraph "Application Layer"
        ReadPath[Read Path<br/>routing.py]
        WritePath[Write Path<br/>write_path.py]
    end
    
    subgraph "Data Layer"
        Redis[(Redis Cache)]
        PostgreSQL[(PostgreSQL<br/>Source of Truth)]
    end
    
    subgraph "Event Layer"
        Kafka[Kafka<br/>route-events Topic]
    end
    
    subgraph "Consumer Layer"
        CacheInv[Cache Invalidation<br/>Consumer]
        Audit[Audit Consumer]
        Other[Other Consumers]
    end
    
    Client -->|Read Request| ReadPath
    Client -->|Write Request| WritePath
    
    ReadPath -->|Cache Check| Redis
    ReadPath -->|Cache Miss| PostgreSQL
    ReadPath -->|Cache Result| Redis
    
    WritePath -->|Transaction| PostgreSQL
    WritePath -->|Publish Event| Kafka
    
    Kafka -->|Events| CacheInv
    Kafka -->|Events| Audit
    Kafka -->|Events| Other
    
    CacheInv -->|Invalidate| Redis
    
    style ReadPath fill:#e1f5ff
    style WritePath fill:#ffe1f5
    style PostgreSQL fill:#fff4e1
    style Redis fill:#ff4e4e
    style Kafka fill:#4eff4e
```

## 2. Read Path Flow

```mermaid
sequenceDiagram
    participant Client
    participant ReadPath
    participant Redis
    participant PostgreSQL
    participant Metrics
    
    Client->>ReadPath: resolve_endpoint(tenant, service, env, version)
    ReadPath->>Metrics: RESOLVE_REQUESTS_TOTAL.inc()
    
    ReadPath->>Redis: GET cache_key
    alt Cache Hit (Positive)
        Redis-->>ReadPath: URL
        ReadPath->>Metrics: CACHE_HIT_TOTAL.inc()
        ReadPath-->>Client: Return URL
    else Cache Hit (Negative)
        Redis-->>ReadPath: __NOT_FOUND__
        ReadPath->>Metrics: NEGATIVE_CACHE_HIT_TOTAL.inc()
        ReadPath-->>Client: RouteNotFoundError
    else Cache Miss
        ReadPath->>Metrics: CACHE_MISS_TOTAL.inc()
        ReadPath->>PostgreSQL: SELECT endpoint WHERE active=true
        alt Route Found
            PostgreSQL-->>ReadPath: URL
            ReadPath->>Redis: SET cache_key, URL (TTL=60s)
            ReadPath-->>Client: Return URL
        else Route Not Found
            PostgreSQL-->>ReadPath: NULL
            ReadPath->>Redis: SET cache_key, __NOT_FOUND__ (TTL=10s)
            ReadPath-->>Client: RouteNotFoundError
        end
    end
    ReadPath->>Metrics: RESOLVE_LATENCY_SECONDS.observe()
```

## 3. Write Path Flow

```mermaid
sequenceDiagram
    participant Client
    participant WritePath
    participant PostgreSQL
    participant Kafka
    participant Metrics
    
    Client->>WritePath: create_route(tenant, service, env, version, url)
    WritePath->>Metrics: WRITE_REQUESTS_TOTAL.inc()
    
    WritePath->>WritePath: Validate inputs
    
    WritePath->>PostgreSQL: BEGIN TRANSACTION
    
    WritePath->>PostgreSQL: INSERT/GET tenant (idempotent)
    WritePath->>PostgreSQL: INSERT/GET service (idempotent)
    WritePath->>PostgreSQL: INSERT/GET environment (idempotent)
    WritePath->>PostgreSQL: INSERT/UPDATE endpoint
    
    alt Transaction Success
        WritePath->>PostgreSQL: COMMIT
        WritePath->>Metrics: WRITE_SUCCESS_TOTAL.inc()
        
        par Kafka Event (Best Effort)
            WritePath->>Kafka: Publish route_changed event
            alt Kafka Success
                Kafka-->>WritePath: ACK
            else Kafka Failure
                Kafka-->>WritePath: Error (logged, non-critical)
            end
        end
        
        WritePath-->>Client: Return route info
    else Transaction Failure
        WritePath->>PostgreSQL: ROLLBACK
        WritePath->>Metrics: WRITE_FAILURE_TOTAL.inc()
        WritePath-->>Client: Return error
    end
    
    WritePath->>Metrics: WRITE_LATENCY_SECONDS.observe()
```

## 4. Database Schema Relationships

```mermaid
erDiagram
    TENANTS ||--o{ SERVICES : "has"
    SERVICES ||--o{ ENVIRONMENTS : "has"
    ENVIRONMENTS ||--o{ ENDPOINTS : "has"
    
    TENANTS {
        int id PK
        string name UK
        timestamp created_at
    }
    
    SERVICES {
        int id PK
        int tenant_id FK
        string name
        timestamp created_at
    }
    
    ENVIRONMENTS {
        int id PK
        int service_id FK
        string name
        timestamp created_at
    }
    
    ENDPOINTS {
        int id PK
        int environment_id FK
        string version
        string url
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }
    
    ROUTE_EVENTS {
        bigint id PK
        string tenant
        string service
        string env
        string version
        string action
        timestamp created_at
        timestamp processed_at
    }
```

## 5. Component Interaction Diagram

```mermaid
graph LR
    subgraph "Read Path Components"
        RP[routing.py]
        RC[Redis Client]
    end
    
    subgraph "Write Path Components"
        WP[write_path.py]
        KC[Kafka Producer]
    end
    
    subgraph "Infrastructure"
        DB[(PostgreSQL)]
        RD[(Redis)]
        KF[Kafka]
    end
    
    subgraph "Observability"
        LG[Logger]
        MT[Metrics]
    end
    
    RP --> RC
    RC --> RD
    RP --> DB
    RP --> LG
    RP --> MT
    
    WP --> DB
    WP --> KC
    KC --> KF
    WP --> LG
    WP --> MT
    
    style RP fill:#e1f5ff
    style WP fill:#ffe1f5
    style DB fill:#fff4e1
    style RD fill:#ff4e4e
    style KF fill:#4eff4e
```

## 6. Event Flow Diagram

```mermaid
graph TD
    WP[Write Path<br/>Transaction Commits]
    KF[Kafka<br/>route-events Topic]
    
    subgraph "Consumers"
        CI[Cache Invalidation<br/>Consumer]
        AU[Audit Consumer]
        OT[Other Consumers]
    end
    
    subgraph "Actions"
        RD[(Redis<br/>Key Deletion)]
        AL[Audit Logs]
        BL[Business Logic]
    end
    
    WP -->|Publish Event| KF
    KF -->|Consume| CI
    KF -->|Consume| AU
    KF -->|Consume| OT
    
    CI -->|Delete| RD
    AU -->|Write| AL
    OT -->|Execute| BL
    
    style WP fill:#ffe1f5
    style KF fill:#4eff4e
    style CI fill:#e1f5ff
    style AU fill:#e1f5ff
    style OT fill:#e1f5ff
```

## 7. Consistency Model Diagram

```mermaid
graph TB
    subgraph "Strong Consistency"
        DB[(PostgreSQL<br/>ACID Transactions)]
        WP[Write Path<br/>Synchronous]
    end
    
    subgraph "Eventual Consistency"
        RD[(Redis Cache<br/>TTL: 60s/10s)]
        KF[Kafka Events<br/>At-least-once]
        CS[Consumers<br/>Async Processing]
    end
    
    WP -->|Immediate| DB
    DB -->|After Commit| KF
    KF -->|Eventually| CS
    CS -->|Eventually| RD
    
    style DB fill:#fff4e1
    style WP fill:#ffe1f5
    style RD fill:#ff4e4e
    style KF fill:#4eff4e
```

## 8. Failure Scenarios

```mermaid
graph TD
    subgraph "Read Path Failures"
        R1[Redis Unavailable]
        R2[Database Unavailable]
        R3[Cache Stale]
    end
    
    subgraph "Write Path Failures"
        W1[Database Failure]
        W2[Kafka Failure]
    end
    
    subgraph "Recovery Actions"
        A1[Fallback to DB]
        A2[Return Error]
        A3[Rollback Transaction]
        A4[Log Warning]
        A5[Cache TTL Expires]
    end
    
    R1 -->|Read Path| A1
    R2 -->|Cache Miss| A2
    R3 -->|Bounded by TTL| A5
    
    W1 -->|Write Path| A3
    W1 -->|Write Path| A2
    W2 -->|Non-Critical| A4
    
    style R1 fill:#ffcccc
    style R2 fill:#ffcccc
    style R3 fill:#ffffcc
    style W1 fill:#ffcccc
    style W2 fill:#ffffcc
```

## 9. Scalability Model

```mermaid
graph TB
    subgraph "Horizontal Scaling"
        RP1[Read Path<br/>Instance 1]
        RP2[Read Path<br/>Instance 2]
        RP3[Read Path<br/>Instance N]
        
        WP1[Write Path<br/>Instance 1]
        WP2[Write Path<br/>Instance 2]
    end
    
    subgraph "Shared Resources"
        RD[(Redis<br/>100K+ req/s)]
        DB[(PostgreSQL<br/>1K-10K writes/s)]
        KF[Kafka<br/>High Throughput]
    end
    
    subgraph "Consumers"
        C1[Consumer 1]
        C2[Consumer 2]
        C3[Consumer N]
    end
    
    RP1 --> RD
    RP2 --> RD
    RP3 --> RD
    RP1 --> DB
    RP2 --> DB
    RP3 --> DB
    
    WP1 --> DB
    WP2 --> DB
    WP1 --> KF
    WP2 --> KF
    
    KF --> C1
    KF --> C2
    KF --> C3
    
    style RP1 fill:#e1f5ff
    style RP2 fill:#e1f5ff
    style RP3 fill:#e1f5ff
    style WP1 fill:#ffe1f5
    style WP2 fill:#ffe1f5
```

## 10. Metrics and Observability

```mermaid
graph LR
    subgraph "Application"
        RP[Read Path]
        WP[Write Path]
    end
    
    subgraph "Metrics"
        RM[Read Metrics<br/>- Requests<br/>- Cache Hits/Misses<br/>- Latency]
        WM[Write Metrics<br/>- Requests<br/>- Success/Failure<br/>- Latency]
    end
    
    subgraph "Logging"
        LG[Logger<br/>- Structured Logs<br/>- Levels: DEBUG/INFO/WARN/ERROR]
    end
    
    subgraph "Export"
        PM[Prometheus<br/>Metrics Endpoint]
        LS[Log Stream]
    end
    
    RP --> RM
    WP --> WM
    RP --> LG
    WP --> LG
    
    RM --> PM
    WM --> PM
    LG --> LS
    
    style RP fill:#e1f5ff
    style WP fill:#ffe1f5
    style PM fill:#4eff4e
    style LS fill:#4eff4e
```

## 11. Cache Strategy Flow

```mermaid
flowchart TD
    Start[Request: resolve_endpoint]
    CheckCache{Check Redis<br/>Cache}
    
    CacheHitPos[Cache Hit<br/>Positive]
    CacheHitNeg[Cache Hit<br/>Negative]
    CacheMiss[Cache Miss]
    
    QueryDB[Query PostgreSQL]
    
    RouteFound[Route Found]
    RouteNotFound[Route Not Found]
    
    CachePos[Cache URL<br/>TTL: 60s]
    CacheNeg[Cache __NOT_FOUND__<br/>TTL: 10s]
    
    ReturnURL[Return URL]
    ReturnError[Return<br/>RouteNotFoundError]
    
    Start --> CheckCache
    CheckCache -->|Found URL| CacheHitPos
    CheckCache -->|Found __NOT_FOUND__| CacheHitNeg
    CheckCache -->|Not Found| CacheMiss
    
    CacheHitPos --> ReturnURL
    CacheHitNeg --> ReturnError
    
    CacheMiss --> QueryDB
    QueryDB -->|Result| RouteFound
    QueryDB -->|No Result| RouteNotFound
    
    RouteFound --> CachePos
    RouteNotFound --> CacheNeg
    
    CachePos --> ReturnURL
    CacheNeg --> ReturnError
    
    style CacheHitPos fill:#90EE90
    style CacheHitNeg fill:#FFB6C1
    style CacheMiss fill:#FFA500
    style ReturnURL fill:#90EE90
    style ReturnError fill:#FFB6C1
```

## 12. Idempotency Model

```mermaid
graph TD
    subgraph "Idempotent Operations"
        CR[create_route]
        AR[activate_route]
        DR[deactivate_route]
    end
    
    subgraph "Idempotency Mechanisms"
        UC[Unique Constraints<br/>Database Level]
        IK[Idempotency Keys<br/>Optional]
        DT[Deterministic Writes<br/>Same Input = Same Output]
    end
    
    subgraph "Guarantees"
        ND[No Duplicates]
        SR[Same Result<br/>on Retry]
    end
    
    CR --> UC
    AR --> DT
    DR --> DT
    
    UC --> ND
    DT --> SR
    IK --> ND
    
    style CR fill:#ffe1f5
    style AR fill:#ffe1f5
    style DR fill:#ffe1f5
    style ND fill:#90EE90
    style SR fill:#90EE90
```

## How to View These Diagrams

These Mermaid diagrams can be viewed in:

1. **GitHub/GitLab**: Rendered automatically in markdown files
2. **VS Code**: Install "Markdown Preview Mermaid Support" extension
3. **Online**: Copy diagram code to [Mermaid Live Editor](https://mermaid.live/)
4. **Documentation Tools**: Most modern documentation platforms support Mermaid

## Diagram Legend

- **Blue boxes**: Read path components
- **Pink boxes**: Write path components
- **Yellow boxes**: Database/storage
- **Red boxes**: Cache
- **Green boxes**: Event/messaging systems
- **Light colors**: Application components
- **Dark colors**: Infrastructure components
