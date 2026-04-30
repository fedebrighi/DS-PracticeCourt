```mermaid
graph TB

    subgraph Client["Client (Browser)"]
        Browser["Browser\nHTTP REST + WebSocket"]
    end
    
    subgraph Compose["Docker Compose - practicecourt"]
    
    subgraph FieldContainer["practicecourt_field :8001"]
        FieldNode["field_node\nFastAPI\n----------------\n2PC Coordinator\nWebSocket Server\nRecovery Loop"]
    end

    subgraph UtilityContainer["practicecourt_utility :8002"]
        UtilityNode["utility_node\nFastAPI\n----------------\n2PC Participant\n/internal/* endpoints"]
    end

    subgraph RedisContainer["practicecourt_redis :6379"]
        Redis["(Redis 7\n----------------\nDistributed Locks\nPub/Sub channel\n2pc:txn state\nhold:* TTL slots)"]
    end

    subgraph MySQLContainer["practicecourt_mysql :3306"]
        MySQL["(MySQL 8.0\npracticecourt\n----------------\nfields\nfield_bookings\nutilities\nutility_bookings)"]
    end

    subgraph SharedVol["./shared (Shared Volume)"]
        Shared["config - db - redis_client\nschemas - models - locks\nevents - logging_config"]
    end
end

Browser -->|"HTTP REST\nGET/POST /fields\nGET/POST /bookings\nPOST /bookings/2pc"| FieldNode
Browser <-->|"WebSocket\nws://:8001/ws/availability\nreal-time events"| FieldNode

FieldNode -->|"HTTP (httpx)\nPOST /internal/prepare\nPOST /internal/commit\nPOST /internal/rollback"| UtilityNode

FieldNode <-->|"SET NX PX - DEL\nPUBLISH - SCAN\nSET 2pc:txn:* - SET hold:*" | Redis
UtilityNode <-->|"SUBSCRIBE\navailability_updates"| Redis

FieldNode -->|"field_bookings\nSELECT / INSERT / UPDATE"| MySQL
UtilityNode -->|"utility_bookings\nSELECT / INSERT / UPDATE"| MySQL

FieldNode -. "import" .-> Shared
UtilityNode -. "import" .-> Shared