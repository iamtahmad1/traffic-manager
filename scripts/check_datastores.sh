#!/bin/bash
# Enhanced script to check all datastores with beautiful formatting
# Shows Redis cache entries and Kafka queue messages

# Colors for beautiful output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Check if live mode is requested
LIVE_MODE=false
if [ "$1" == "--live" ] || [ "$1" == "-l" ]; then
    LIVE_MODE=true
fi

# Function to clear screen and show header
show_header() {
    clear
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  ${BOLD}Traffic Manager - Datastore Status Monitor${NC}                    ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Function to check PostgreSQL
check_postgresql() {
    echo -e "${BOLD}${BLUE}┌─ PostgreSQL Database${NC}"
    if docker exec postgres psql -U app_user -d app_db -c "SELECT 1;" > /dev/null 2>&1; then
        echo -e "${GREEN}│  ✓ PostgreSQL is accessible${NC}"
        
        # Get endpoint count
        ENDPOINT_COUNT=$(docker exec postgres psql -U app_user -d app_db -t -c "SELECT COUNT(*) FROM endpoints;" 2>/dev/null | tr -d ' ' | tr -d '\r')
        echo -e "${CYAN}│  📊 Active Routes: ${BOLD}${ENDPOINT_COUNT}${NC}"
        
        # Get recent routes
        echo -e "${CYAN}│  Recent Routes:${NC}"
        docker exec postgres psql -U app_user -d app_db -t -A -F"|" -c "
            SELECT 
                t.name as tenant,
                s.name as service,
                env.name as env,
                e.version,
                e.url,
                CASE WHEN e.is_active THEN '✓' ELSE '✗' END as status
            FROM tenants t
            JOIN services s ON s.tenant_id = t.id
            JOIN environments env ON env.service_id = s.id
            JOIN endpoints e ON e.environment_id = env.id
            ORDER BY e.updated_at DESC
            LIMIT 5;
        " 2>/dev/null | while IFS='|' read -r tenant service env version url status; do
            tenant=$(echo "$tenant" | xargs)
            service=$(echo "$service" | xargs)
            env=$(echo "$env" | xargs)
            version=$(echo "$version" | xargs)
            url=$(echo "$url" | xargs)
            status=$(echo "$status" | xargs)
            if [ ! -z "$tenant" ] && [ "$tenant" != "tenant" ]; then
                echo -e "${CYAN}│    ${status} ${tenant}/${service}/${env}/${version} → ${url}${NC}"
            fi
        done
    else
        echo -e "${RED}│  ✗ PostgreSQL is not accessible${NC}"
    fi
    echo -e "${BLUE}└────────────────────────────────────────────────────────────────${NC}"
    echo ""
}

# Function to check Redis Cache
check_redis() {
    echo -e "${BOLD}${MAGENTA}┌─ Redis Cache${NC}"
    if docker exec redis redis-cli PING > /dev/null 2>&1; then
        echo -e "${GREEN}│  ✓ Redis is accessible${NC}"
        
        # Get total keys
        KEY_COUNT=$(docker exec redis redis-cli DBSIZE 2>/dev/null | tr -d '\r')
        echo -e "${CYAN}│  📊 Total Keys: ${BOLD}${KEY_COUNT}${NC}"
        
        # Get route cache entries
        ROUTE_KEYS=$(docker exec redis redis-cli KEYS "route:*" 2>/dev/null)
        # Count properly - handle empty result
        if [ -z "$ROUTE_KEYS" ]; then
            ROUTE_COUNT=0
        else
            ROUTE_COUNT=$(echo "$ROUTE_KEYS" | grep -v "^$" | wc -l | tr -d ' ')
        fi
        echo -e "${CYAN}│  📦 Route Cache Entries: ${BOLD}${ROUTE_COUNT}${NC}"
        
        if [ "$ROUTE_COUNT" -gt 0 ]; then
            echo -e "${CYAN}│  Cache Entries:${NC}"
            echo "$ROUTE_KEYS" | head -10 | while read -r key; do
                if [ ! -z "$key" ]; then
                    # Get value and TTL
                    VALUE=$(docker exec redis redis-cli GET "$key" 2>/dev/null | tr -d '\r')
                    TTL=$(docker exec redis redis-cli TTL "$key" 2>/dev/null | tr -d '\r')
                    
                    # Format key (remove "route:" prefix for display)
                    DISPLAY_KEY=$(echo "$key" | sed 's/^route://')
                    
                    if [ "$VALUE" == "__NOT_FOUND__" ]; then
                        echo -e "${YELLOW}│    ✗ ${DISPLAY_KEY} (negative cache, TTL: ${TTL}s)${NC}"
                    else
                        # Truncate long URLs
                        SHORT_URL=$(echo "$VALUE" | cut -c1-50)
                        if [ ${#VALUE} -gt 50 ]; then
                            SHORT_URL="${SHORT_URL}..."
                        fi
                        echo -e "${GREEN}│    ✓ ${DISPLAY_KEY}${NC}"
                        echo -e "${CYAN}│      → ${SHORT_URL} (TTL: ${TTL}s)${NC}"
                    fi
                fi
            done
            
            if [ "$ROUTE_COUNT" -gt 10 ]; then
                REMAINING=$((ROUTE_COUNT - 10))
                echo -e "${CYAN}│    ... and ${REMAINING} more entries${NC}"
            fi
        else
            echo -e "${YELLOW}│  ⚠ No route cache entries found${NC}"
        fi
    else
        echo -e "${RED}│  ✗ Redis is not accessible${NC}"
    fi
    echo -e "${MAGENTA}└────────────────────────────────────────────────────────────────${NC}"
    echo ""
}

# Function to check Kafka
check_kafka() {
    echo -e "${BOLD}${YELLOW}┌─ Kafka Event Queue${NC}"
    # Check if Kafka container is running
    if ! docker ps --format "{{.Names}}" | grep -q "^kafka$"; then
        echo -e "${RED}│  ✗ Kafka container is not running${NC}"
        echo -e "${YELLOW}└────────────────────────────────────────────────────────────────${NC}"
        echo ""
        return
    fi
    
    # Try to list topics (Confluent Kafka uses kafka-topics without .sh)
    if docker exec kafka /bin/sh -c "kafka-topics --bootstrap-server localhost:9092 --list" > /dev/null 2>&1; then
        echo -e "${GREEN}│  ✓ Kafka is accessible${NC}"
        
        # Check if route-events topic exists
        TOPIC_LIST=$(docker exec kafka /bin/sh -c "kafka-topics --bootstrap-server localhost:9092 --list" 2>/dev/null)
        TOPIC_EXISTS=$(echo "$TOPIC_LIST" | grep -c "route-events" || echo "0")
        
        if [ "$TOPIC_EXISTS" -gt 0 ]; then
            # Get topic details
            TOPIC_INFO=$(docker exec kafka /bin/sh -c "kafka-topics --bootstrap-server localhost:9092 --describe --topic route-events" 2>/dev/null)
            PARTITIONS=$(echo "$TOPIC_INFO" | grep -c "Partition:" || echo "0")
            echo -e "${CYAN}│  📊 Topic: route-events (${PARTITIONS} partitions)${NC}"
            
            # Get consumer groups (try kafka-consumer-groups)
            echo -e "${CYAN}│  Consumer Groups:${NC}"
            CONSUMER_GROUPS=$(docker exec kafka /bin/sh -c "kafka-consumer-groups --bootstrap-server localhost:9092 --list" 2>/dev/null)
            if [ ! -z "$CONSUMER_GROUPS" ] && [ "$CONSUMER_GROUPS" != "" ]; then
                echo "$CONSUMER_GROUPS" | grep -v "^$" | while read -r group; do
                    if [ ! -z "$group" ]; then
                        echo -e "${CYAN}│    • ${group}${NC}"
                    fi
                done
            else
                echo -e "${YELLOW}│    ⚠ No active consumer groups${NC}"
            fi
            
            # Try to get recent messages (last 5)
            echo -e "${CYAN}│  Recent Messages (last 5):${NC}"
            # Use kafka-console-consumer to peek at messages
            # Note: This might take a moment, so we use timeout
            RECENT_MSGS=$(timeout 3 docker exec kafka /bin/sh -c "kafka-console-consumer --topic route-events --from-beginning --max-messages 5 --bootstrap-server localhost:9092 2>/dev/null" || echo "")
            
            if [ ! -z "$RECENT_MSGS" ] && [ "$RECENT_MSGS" != "" ]; then
                echo "$RECENT_MSGS" | head -5 | while read -r msg; do
                    if [ ! -z "$msg" ] && [ "$msg" != "" ]; then
                        # Try to parse JSON and extract key fields
                        ACTION=$(echo "$msg" | grep -o '"action":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
                        TENANT=$(echo "$msg" | grep -o '"tenant":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
                        SERVICE=$(echo "$msg" | grep -o '"service":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
                        ENV=$(echo "$msg" | grep -o '"env":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
                        VERSION=$(echo "$msg" | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
                        
                        if [ "$ACTION" != "unknown" ] && [ "$TENANT" != "unknown" ]; then
                            echo -e "${GREEN}│    ✓ ${ACTION}: ${TENANT}/${SERVICE}/${ENV}/${VERSION}${NC}"
                        else
                            # Show truncated message if can't parse
                            SHORT_MSG=$(echo "$msg" | cut -c1-60)
                            if [ ! -z "$SHORT_MSG" ]; then
                                echo -e "${CYAN}│    • ${SHORT_MSG}...${NC}"
                            fi
                        fi
                    fi
                done
            else
                echo -e "${YELLOW}│    ⚠ No messages in queue (or topic is empty)${NC}"
            fi
        else
            echo -e "${YELLOW}│  ⚠ Topic 'route-events' does not exist${NC}"
            echo -e "${CYAN}│    Create it with:${NC}"
            echo -e "${CYAN}│    docker exec kafka kafka-topics --create \\${NC}"
            echo -e "${CYAN}│      --topic route-events --bootstrap-server localhost:9092 \\${NC}"
            echo -e "${CYAN}│      --partitions 3 --replication-factor 1${NC}"
        fi
    else
        echo -e "${RED}│  ✗ Kafka is not accessible (container may be starting)${NC}"
    fi
    echo -e "${YELLOW}└────────────────────────────────────────────────────────────────${NC}"
    echo ""
}

# Function to check MongoDB
check_mongodb() {
    echo -e "${BOLD}${BLUE}┌─ MongoDB Audit Store${NC}"
    # Check if MongoDB container is running
    if ! docker ps --format "{{.Names}}" | grep -q "^mongodb$"; then
        echo -e "${RED}│  ✗ MongoDB container is not running${NC}"
        echo -e "${BLUE}└────────────────────────────────────────────────────────────────${NC}"
        echo ""
        return
    fi
    
    # Try to ping MongoDB
    if docker exec mongodb mongosh -u admin -p admin_password --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        echo -e "${GREEN}│  ✓ MongoDB is accessible${NC}"
        
        # Get audit event count
        AUDIT_COUNT=$(docker exec mongodb mongosh -u admin -p admin_password --quiet --eval "db.route_events.countDocuments()" audit_db 2>/dev/null | tr -d '\r' | tr -d '\n')
        if [ -z "$AUDIT_COUNT" ] || [ "$AUDIT_COUNT" == "null" ]; then
            AUDIT_COUNT=0
        fi
        echo -e "${CYAN}│  📊 Total Audit Events: ${BOLD}${AUDIT_COUNT}${NC}"
        
        if [ "$AUDIT_COUNT" -gt 0 ]; then
            echo -e "${CYAN}│  Recent Events:${NC}"
            # Get recent events using mongosh
            docker exec mongodb mongosh -u admin -p admin_password --quiet audit_db --eval "
                db.route_events.find()
                    .sort({occurred_at: -1})
                    .limit(5)
                    .forEach(function(doc) {
                        var action = doc.action || 'unknown';
                        var route = doc.route || {};
                        var tenant = route.tenant || 'unknown';
                        var service = route.service || 'unknown';
                        var env = route.env || 'unknown';
                        var version = route.version || 'unknown';
                        var time = doc.occurred_at ? doc.occurred_at.toISOString().substr(11, 8) : 'unknown';
                        print(action + '|' + tenant + '|' + service + '|' + env + '|' + version + '|' + time);
                    });
            " 2>/dev/null | while IFS='|' read -r action tenant service env version time; do
                if [ ! -z "$action" ] && [ "$action" != "null" ]; then
                    case "$action" in
                        "created")
                            ICON="➕"
                            COLOR="${GREEN}"
                            ;;
                        "activated")
                            ICON="✅"
                            COLOR="${GREEN}"
                            ;;
                        "deactivated")
                            ICON="❌"
                            COLOR="${RED}"
                            ;;
                        *)
                            ICON="📝"
                            COLOR="${CYAN}"
                            ;;
                    esac
                    echo -e "${COLOR}│    ${ICON} ${action} - ${tenant}/${service}/${env}/${version} (${time})${NC}"
                fi
            done
        else
            echo -e "${YELLOW}│  ⚠ No audit log entries yet${NC}"
        fi
        
        # Get collection stats
        COLLECTION_STATS=$(docker exec mongodb mongosh -u admin -p admin_password --quiet audit_db --eval "db.route_events.stats().size" 2>/dev/null | tr -d '\r' | tr -d '\n')
        if [ ! -z "$COLLECTION_STATS" ] && [ "$COLLECTION_STATS" != "null" ] && [ "$COLLECTION_STATS" != "undefined" ]; then
            SIZE_KB=$((COLLECTION_STATS / 1024))
            echo -e "${CYAN}│  💾 Collection Size: ${BOLD}${SIZE_KB} KB${NC}"
        fi
    else
        echo -e "${RED}│  ✗ MongoDB is not accessible${NC}"
    fi
    echo -e "${BLUE}└────────────────────────────────────────────────────────────────${NC}"
    echo ""
}

# Function to show audit log (deprecated - now using MongoDB)
check_audit_log() {
    echo -e "${BOLD}${GREEN}┌─ Audit Log (PostgreSQL - Deprecated)${NC}"
    echo -e "${YELLOW}│  ⚠ Note: Audit logs are now stored in MongoDB${NC}"
    echo -e "${YELLOW}│     See MongoDB section above for current audit data${NC}"
    if docker exec postgres psql -U app_user -d app_db -c "SELECT 1;" > /dev/null 2>&1; then
        # Check if route_events table still exists
        TABLE_EXISTS=$(docker exec postgres psql -U app_user -d app_db -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'route_events');" 2>/dev/null | tr -d ' ' | tr -d '\r')
        if [ "$TABLE_EXISTS" == "t" ]; then
            AUDIT_COUNT=$(docker exec postgres psql -U app_user -d app_db -t -c "SELECT COUNT(*) FROM route_events;" 2>/dev/null | tr -d ' ' | tr -d '\r')
            echo -e "${CYAN}│  📊 Legacy Events (PostgreSQL): ${BOLD}${AUDIT_COUNT}${NC}"
        else
            echo -e "${CYAN}│  📊 Legacy Events: ${BOLD}0${NC} (table removed)${NC}"
        fi
    else
        echo -e "${RED}│  ✗ Cannot access database${NC}"
    fi
    echo -e "${GREEN}└────────────────────────────────────────────────────────────────${NC}"
    echo ""
}

# Main function
main() {
    if [ "$LIVE_MODE" = true ]; then
        # Live mode - refresh every 2 seconds
        while true; do
            show_header
            check_postgresql
            check_redis
            check_mongodb
            check_kafka
            check_audit_log
            echo -e "${BOLD}${CYAN}Press Ctrl+C to exit live mode${NC}"
            sleep 2
        done
    else
        # Single run
        show_header
        check_postgresql
        check_redis
        check_mongodb
        check_kafka
        check_audit_log
        echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${BOLD}${CYAN}║${NC}  ${BOLD}Tip:${NC} Run with ${BOLD}--live${NC} or ${BOLD}-l${NC} for real-time updates:              ${BOLD}${CYAN}║${NC}"
        echo -e "${BOLD}${CYAN}║${NC}        ${BOLD}./scripts/check_datastores.sh --live${NC}                          ${BOLD}${CYAN}║${NC}"
        echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    fi
}

# Run main function
main
