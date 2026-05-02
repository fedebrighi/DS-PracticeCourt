```mermaid
flowchart TD
    START([recovery_loop started])
    START --> SLEEP["sleep 60s"]
    SLEEP --> RUN["run_recovery()\ncreate standalone Redis client"]
    RUN --> SCAN["scan transaction keys"]
    
    SCAN --> CHECKKEY{"Matching key found?"}
    CHECKKEY -->|NO| CLOSE["close Redis client"]
    CLOSE --> SLEEP
    
    CHECKKEY -->|YES| READKEY["read transaction state\nand utility_booking_ids"]
    READKEY --> CHECKSTATE{"state == PREPARED?"}
    
    CHECKSTATE -->|NO| SCAN
    CHECKSTATE -->|YES| RECOVER["recover prepared transaction"]
    
    RECOVER --> COMMIT["POST /internal/commit\nto utility_node"]
    COMMIT --> SUCCESS{"Commit response OK?"}
    
    SUCCESS -->|YES| CONFIRM["mark FieldBooking CONFIRMED\n and delete Redis key"]
        CONFIRM --> LOG1["[RECOVERY] booking confirmed"]
        LOG1 --> SCAN
        
    SUCCESS -->|NO| ROLLBACK["rollback utilities\nbest-effort"]
        ROLLBACK --> FAIL["mark FieldBooking FAILED\n and delete Redis key"]
        FAIL --> LOG2["[RECOVERY] booking failed"]
        LOG2 --> SCAN