```mermaid
graph TB
    subgraph shared[" shared/ (Volume mounted in both containers)"]
        direction LR
        config["config.py\nSettings - get_settings()\nDB_URL - REDIS_URL - UTILITY_NODE_URL"]
        db["db.py\nDatabaseSessionManager\nget_db() - session()"]
        redis_c["redis_client.py\nRedisClientManager\nget_redis() - create_pubsub_client()\nget_client()"]
        schemas["schemas.py\nBookingStatus - TwoPCTransactionState\nTwoPCVote - FieldBookingRequest\nPrepareRequest - PrepareResponse"]
        models["models.py\nField - FieldBooking\nUtility - UtilityBooking"]
        locks["locks.py\nDistributedLock\nacquire() SET NX PX\nrelease() Lua script"]
        events["events.py\nAVAILABILITY_CHANNEL\npublish_booking_event()"]
        logging_c["logging_config.py\nsetup_logging(node_name)"]
    end
    
    subgraph field_node
        direction TB
        main_f["main.py\nFastAPI lifespan\nGET/POST /fields\nGET/POST /bookings\nPOST /bookings/2pc\nPOST /admin/recovery\nGET /ws/availability"]
        coord["two_pc_coordinator.py\nprepare_all()\ncommit_all()\nrollback_all()\n_set_txn_state()"]
        recovery["recovery.py\nrecovery_loop()\nrun_recovery()\n_recover_one()"]
        subgraph repos_f["repositories/"]
            fr["field_repository.py\nget_all() - get_by_id()"]
            fbr["field_booking_repository.py\ncreate() - check_availability()\ncreate_pending() - update_status()"]
        end
    end
    
    subgraph utility_node
        direction TB
        main_u["main.py\nFastAPI lifespan\nGET/POST /utilities\nGET /utility-bookings\nPOST /internal/prepare\nPOST /internal/commit\nPOST /internal/rollback"]
        subgraph repos_u["repositories/"]
            ur["utility_repository.py\nget_all() - get_by_id()"]
            ubr["utility_booking_repository.py\n\nupdate_status()"]
        end
    end
    
    main_f --> coord
    main_f --> recovery
    main_f --> fr
    main_f --> fbr
    coord -->|"HTTP httpx\n_HTTP_TIMEOUT=5s"| main_u
    recovery -->|"HTTP httpx\nre-commit / rollback"| main_u
    main_u --> ur
    main_u --> ubr

    field_node -. "import" .-> config
    field_node -. "import" .-> db
    field_node -. "import" .-> redis_c
    field_node -. "import" .-> schemas
    field_node -. "import" .-> models
    field_node -. "import" .-> locks
    field_node -. "import" .-> events
    field_node -. "import" .-> logging_c

    utility_node -. "import" .-> config
    utility_node -. "import" .-> db
    utility_node -. "import" .-> redis_c
    utility_node -. "import" .-> schemas
    utility_node -. "import" .-> models
    utility_node -. "import" .-> logging_c
     

