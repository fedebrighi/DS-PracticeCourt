```mermaid
stateDiagram-v2
    direction LR
    
    [*] --> PENDING : create() or create_pending() 
    
    PENDING --> CONFIRMED : 2PC commit OK update_status(CONFIRMED) or recovery -> CONFIRMED
    PENDING --> FAILED : 2PC at least one NO rollback 2PC or recovery -> FAILED update_status(FAILED)
    PENDING --> CANCELLED : explicit cancellation before confirmation
    
    CONFIRMED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
     