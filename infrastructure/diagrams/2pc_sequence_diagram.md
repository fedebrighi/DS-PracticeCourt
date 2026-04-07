```mermaid
sequenceDiagram
    participant C as Client
    participant FN as field_node (Coordinator :8001)
    participant R as Redis
    participant DB_F as MySQL [field_bookings]
    participant UN as utility_node (Partecipant :8002)
    participant DB_U as MySQL [utility_bookings]

    C->>FN: POST /bookings/2pc<br/>{field_id, user_id, start, end, utility_ids}
    
    Note over FN,R: Acquire distributed lock
    FN->>R: SET lock:field:{field_id} NX PX 5000
    R-->>FN: token (lock acquisito)

    FN->>DB_F: SELECT - check_availability(field_id, start, end)
    DB_F-->>FN: available = True
    
    FN->>DB_F: INSERT FieldBooking (status=PENDING)
    DB_F-->>FN: field_booking_id = 42

    FN->>R: SET 2pc:txn:42 {"state":"init", "utility_booking_ids":[]} EX 300

    Note over FN,UN: PHASE 1: PREPARE

    loop per ogni utility_id in utility_ids
        FN->>UN: POST /internal/prepare<br/>{field_booking_id:42, utility_id}
        UN->>DB_U: SELECT Utility - check is_active
        DB_U-->>UN: utility.is_active = True
        UN->>DB_U: INSERT UtilityBooking (status=PENDING)
        DB_U-->>UN: utility_booking_id
        UN-->>FN: {"vote":"yes", utility_booking_id}
    end
    
    alt Tutti YES
        Note over FN,UN: PHASE 2: COMMIT 

        FN->>R: SET 2pc:txn:42 {"state":"prepared", "utility_booking_ids":[7, 8]} EX 300
    
        FN->>UN: POST /internal/commit<br/>{field_booking_id:42, utility_booking_ids:[7, 8]}
        UN->>DB_U: UPDATE UtilityBooking 7,8 -> CONFIRMED
        UN-->>FN: {ok: true}

        FN->>DB_F: UPDATE FieldBooking 42 -> CONFIRMED
        FN->>R: SET 2pc:txn:42 {"state":"committed", ...} EX 300
        FN->>R: DEL lock:field:{field_id} (release)
        FN-->> C: 201 Created (Booking Confirmed)

    else Almeno un NO o Timeout
        Note over FN,UN: PHASE 2: ROLLBACK
        FN->>UN: POST /internal/rollback<br/>{field_booking_id:42, utility_booking_ids:[7]}
        UN->>DB_U: UPDATE UtilityBooking 7 -> CANCELLED
        UN-->>FN: {ok: true}

        FN->>DB_F: UPDATE FieldBooking 42 -> CANCELLED
        FN->>R: SET 2pc:txn:42 {"state":"aborted", ...} EX 300
        FN->>R: DEL lock:field:{field_id} (release)
        FN-->> C: 409 Conflict (Booking Failed)
    end