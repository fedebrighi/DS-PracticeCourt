```mermaid
stateDiagram-v2
    direction LR

    [*] --> INIT : prepare_all() invoked state=INIT
    
    INIT --> PREPARED: all partecipants vote YES SET state=PREPARED
    INIT --> ABORTED: at least a partecipant votes NO or timeout SET state=ABORTED
    PREPARED --> COMMITTED : commit_all() OK SET state=COMMITTED
    PREPARED --> ABORTED : recovery fails or utility_node unreachable SET state=ABORTED
    COMMITTED --> [*] : transaction closed
    ABORTED --> [*] : transaction closed
    