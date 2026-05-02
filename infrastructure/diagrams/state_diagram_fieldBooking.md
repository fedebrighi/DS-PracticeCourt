```mermaid
stateDiagram-v2
    direction LR
    
    [*] --> PENDING : create() or create_pending() 
    
    PENDING --> CONFIRMED : 2PC commit OK\nupdate_status(CONFIRMED)\n or recovery -> CONFIRMED
    PENDING --> FAILED : 2PC at least one NO\n rollback 2PC\n or recovery -> FAILED\nupdate_status(FAILED)
    PENDING --> CANCELLED : explicit cancellation\nbefore confirmation
    
    CONFIRMED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
     