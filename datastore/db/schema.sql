CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);


CREATE TABLE services (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);


CREATE TABLE environments (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id),
    name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (service_id, name)
);


CREATE TABLE endpoints (
    id SERIAL PRIMARY KEY,
    environment_id INTEGER NOT NULL REFERENCES environments(id),
    version TEXT NOT NULL,
    url TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),

    UNIQUE (environment_id, version)
);

CREATE INDEX idx_tenants_name ON tenants(name);
CREATE INDEX idx_services_tenant ON services(tenant_id);
CREATE INDEX idx_env_service ON environments(service_id);
CREATE INDEX idx_endpoints_env_active ON endpoints(environment_id, is_active);

CREATE TABLE route_events (
    id BIGSERIAL PRIMARY KEY,
    tenant TEXT NOT NULL,
    service TEXT NOT NULL,
    env TEXT NOT NULL,
    version TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('created', 'activated', 'deactivated')),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    processed_at TIMESTAMP
);
