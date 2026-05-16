```mermaid
sequenceDiagram
    participant C as Client
    participant FN as Field Node
    participant R as Redis
    participant UN as Utility Node

    C->>FN: POST /bookings/2pc
    FN->>R: Acquire distributed lock

    loop for each requested utility
        FN->>UN: /internal/prepare
        UN-->>FN: vote yes/no
    end
    
    alt All votes are YES
        FN->>UN: /internal/commit
        FN->>R: Store committed transaction sate
        FN-->> C: Booking Confirmed

    else At least one vot is NO o Timeout
        FN->>UN: /internal/rollback
        FN->>R: Store aborted transaction state
        FN-->> C: Booking Failed
    end