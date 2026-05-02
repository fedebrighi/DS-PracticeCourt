```mermaid
stateDiagram-v2
    direction LR

    [*] --> INIT : prepare_all() invoked\nstate=INIT
    
    INIT --> PREPARED: all partecipants vote YES\nSET state=PREPARED
    INIT --> ABORTED: at least a partecipant\nvotes NO or timeout\nSET state=ABORTED
    PREPARED --> COMMITTED : commit_all() OK\nSET state=COMMITTED
    PREPARED --> ABORTED : recovery fails or\n utility_node unreachable\nSET state=ABORTED
    COMMITTED --> [*] : transaction closed
    ABORTED --> [*] : transaction closed
    