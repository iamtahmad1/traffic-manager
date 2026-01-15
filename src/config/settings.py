# src/config/settings.py
# This file provides centralized configuration management for the entire application
# In production systems, configuration is managed in one place rather than scattered across files
# This makes it easier to:
# - Change settings without modifying code
# - Have different configs for dev/staging/prod
# - Validate configuration values
# - Provide sensible defaults

import os
from typing import Optional
from dataclasses import dataclass

# dataclass is a Python feature that automatically generates special methods
# like __init__, __repr__, etc. for classes that just hold data
# It's like a struct in C or a simple class that just stores values

@dataclass
class DatabaseConfig:
    """
    Database configuration settings.
    
    This class holds all database-related configuration like host, port, credentials.
    Using a class makes it easy to access: settings.db.host instead of settings['db']['host']
    """
    # Host is where the database server is running
    # Default to 'localhost' for local development
    host: str = os.getenv("DB_HOST", "localhost")
    
    # Port is like a door number - PostgreSQL default is 5432
    # int() converts the string from environment to a number
    port: int = int(os.getenv("DB_PORT", "5432"))
    
    # Database name - which database to connect to
    # PostgreSQL can have multiple databases on the same server
    name: str = os.getenv("DB_NAME", "app_db")
    
    # Username for authentication
    user: str = os.getenv("DB_USER", "app_user")
    
    # Password for authentication
    # In production, this should come from a secrets manager, not environment variables
    password: str = os.getenv("DB_PASSWORD", "super_secret_password")
    
    # Connection pool settings
    # Pool is a collection of reusable database connections
    # Instead of creating a new connection each time, we reuse existing ones
    min_connections: int = int(os.getenv("DB_POOL_MIN", "2"))  # Minimum connections to keep
    max_connections: int = int(os.getenv("DB_POOL_MAX", "10"))  # Maximum connections allowed
    
    # Connection timeout - how long to wait for a connection from the pool
    # If pool is full and we wait longer than this, raise an error
    connection_timeout: int = int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))


@dataclass
class RedisConfig:
    """
    Redis cache configuration settings.
    
    Redis is our caching layer - it stores frequently accessed data in memory
    for fast retrieval without hitting the database.
    """
    # Redis server host
    host: str = os.getenv("REDIS_HOST", "localhost")
    
    # Redis server port (default is 6379)
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    
    # Redis database number (Redis supports multiple logical databases, 0-15)
    # We use database 0 by default
    db: int = int(os.getenv("REDIS_DB", "0"))
    
    # Connection timeout - how long to wait when connecting to Redis
    socket_timeout: int = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
    
    # Connection pool settings for Redis
    # Redis connections can also be pooled for better performance
    max_connections: int = int(os.getenv("REDIS_POOL_MAX", "50"))


@dataclass
class MongoDBConfig:
    """
    MongoDB audit store configuration settings.
    
    MongoDB is used for storing audit logs and change history.
    It provides flexible schema and efficient querying for audit data.
    """
    # MongoDB server host
    host: str = os.getenv("MONGODB_HOST", "localhost")
    
    # MongoDB server port (default is 27017)
    port: int = int(os.getenv("MONGODB_PORT", "27017"))
    
    # Database name - which database to use for audit logs
    name: str = os.getenv("MONGODB_DB", "audit_db")
    
    # Username for authentication
    user: str = os.getenv("MONGODB_USER", "admin")
    
    # Password for authentication
    password: str = os.getenv("MONGODB_PASSWORD", "admin_password")
    
    # Collection name for route audit events
    audit_collection: str = os.getenv("MONGODB_AUDIT_COLLECTION", "route_events")
    
    # Connection timeout - how long to wait when connecting to MongoDB
    connect_timeout_ms: int = int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "5000"))
    
    # Server selection timeout - how long to wait for server selection
    server_selection_timeout_ms: int = int(os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "5000"))


@dataclass
class KafkaConfig:
    """
    Kafka event streaming configuration.
    
    Kafka is our message queue - it handles asynchronous event publishing
    for decoupling the write path from side effects (like cache invalidation).
    """
    # Bootstrap servers - list of Kafka broker addresses
    # In a cluster, you provide multiple brokers for redundancy
    # Format: "host1:port1,host2:port2"
    bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    # Topic name where we publish route change events
    # Topics are like categories or channels in Kafka
    route_events_topic: str = os.getenv("KAFKA_ROUTE_EVENTS_TOPIC", "route-events")
    
    # Producer settings
    # acks='all' means wait for all replicas to acknowledge (most reliable)
    acks: str = os.getenv("KAFKA_ACKS", "all")
    
    # Retry settings - how many times to retry if sending fails
    retries: int = int(os.getenv("KAFKA_RETRIES", "3"))
    
    # Idempotent producer - prevents duplicate messages if we retry
    # This is important for exactly-once semantics (best effort)
    idempotent: bool = os.getenv("KAFKA_IDEMPOTENT", "true").lower() == "true"
    
    # Request timeout - how long to wait for Kafka to respond
    request_timeout_ms: int = int(os.getenv("KAFKA_REQUEST_TIMEOUT_MS", "10000"))

    # Consumer settings
    # Group prefix keeps related consumers together (scalable pattern)
    consumer_group_prefix: str = os.getenv("KAFKA_CONSUMER_GROUP_PREFIX", "traffic-manager")
    # Where to start reading if no offset exists: earliest or latest
    consumer_auto_offset_reset: str = os.getenv("KAFKA_CONSUMER_AUTO_OFFSET_RESET", "earliest")
    # Whether the consumer commits offsets automatically
    consumer_enable_auto_commit: bool = os.getenv("KAFKA_CONSUMER_AUTO_COMMIT", "true").lower() == "true"
    # How long to wait for messages in each poll (ms)
    consumer_poll_timeout_ms: int = int(os.getenv("KAFKA_CONSUMER_POLL_TIMEOUT_MS", "1000"))


@dataclass
class AppConfig:
    """
    Application-level configuration.
    
    Settings that affect how the application behaves, not specific to databases or caches.
    """
    # Environment: development, staging, production
    # This affects logging levels, error handling, etc.
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    # DEBUG shows everything, INFO shows important stuff, etc.
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # API settings
    # Host and port where the API server will listen
    api_host: str = os.getenv("API_HOST", "0.0.0.0")  # 0.0.0.0 means listen on all interfaces
    api_port: int = int(os.getenv("API_PORT", "8000"))
    
    # Debug mode - enables detailed error messages, auto-reload, etc.
    # Should be False in production for security
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Cache TTL settings (Time To Live - how long data stays in cache)
    # Positive cache: when route exists, cache for 60 seconds
    positive_cache_ttl: int = int(os.getenv("CACHE_POSITIVE_TTL", "60"))
    
    # Negative cache: when route doesn't exist, cache for 10 seconds (shorter)
    # Shorter because route might be created soon
    negative_cache_ttl: int = int(os.getenv("CACHE_NEGATIVE_TTL", "10"))


@dataclass
class Settings:
    """
    Main settings class that holds all configuration.
    
    This is a single object that contains all configuration for the entire application.
    Other modules import this and access settings like:
    - settings.db.host
    - settings.redis.port
    - settings.kafka.bootstrap_servers
    
    This pattern is called "configuration as code" - all settings in one place.
    """
    # Database configuration
    db: DatabaseConfig = DatabaseConfig()
    
    # Redis cache configuration
    redis: RedisConfig = RedisConfig()
    
    # MongoDB audit store configuration
    mongodb: MongoDBConfig = MongoDBConfig()
    
    # Kafka configuration
    kafka: KafkaConfig = KafkaConfig()
    
    # Application configuration
    app: AppConfig = AppConfig()
    
    def validate(self):
        """
        Validate configuration values.
        
        This method checks that all required settings are present and valid.
        In production, you'd want to validate:
        - Required fields are not empty
        - Ports are valid numbers
        - URLs are valid format
        - etc.
        
        For now, we do basic validation. In production, you might use a library
        like pydantic for more robust validation.
        """
        # Validate database settings
        if not self.db.host:
            raise ValueError("DB_HOST is required")
        if not (1 <= self.db.port <= 65535):
            raise ValueError(f"DB_PORT must be between 1 and 65535, got {self.db.port}")
        if not self.db.name:
            raise ValueError("DB_NAME is required")
        if not self.db.user:
            raise ValueError("DB_USER is required")
        
        # Validate Redis settings
        if not (1 <= self.redis.port <= 65535):
            raise ValueError(f"REDIS_PORT must be between 1 and 65535, got {self.redis.port}")
        
        # Validate MongoDB settings
        if not (1 <= self.mongodb.port <= 65535):
            raise ValueError(f"MONGODB_PORT must be between 1 and 65535, got {self.mongodb.port}")
        if not self.mongodb.name:
            raise ValueError("MONGODB_DB is required")
        
        # Validate Kafka settings
        if not self.kafka.bootstrap_servers:
            raise ValueError("KAFKA_BOOTSTRAP_SERVERS is required")
        
        # Validate app settings
        if self.app.environment not in ["development", "staging", "production"]:
            raise ValueError(f"ENVIRONMENT must be development, staging, or production, got {self.app.environment}")
        
        if self.app.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL, got {self.app.log_level}")


# Create a global settings instance
# This is a singleton pattern - there's only one settings object in the entire application
# All modules import this same object, so configuration is consistent everywhere
settings = Settings()

# Validate settings when module is imported
# This catches configuration errors early, before the application starts
try:
    settings.validate()
except ValueError as e:
    # In production, you might want to log this and continue with defaults
    # For now, we'll raise the error so developers know something is wrong
    raise RuntimeError(f"Invalid configuration: {e}") from e
