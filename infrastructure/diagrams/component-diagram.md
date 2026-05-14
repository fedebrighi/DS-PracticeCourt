```mermaid
graph TB

    subgraph Client["Web Client"]
        UI["Booking UI"]
        WS["WebSocket Listener"]
    end

    subgraph Field["Field Node (Coordinator)"]
        FAPI["Public Booking APIs"]
        FCOORD["2PC Coordinator & Recovery"]
        FREPO["Field Repository"]
        FBREPO["Field Booking Repository"]
    end

    subgraph Utility["Utility Node (Participant)"]
        UAPI["Internal 2PC APIs"]
        UREPO["Utility Repository"]
        UBREPO["Utility Booking Repository"]
    end

    subgraph Shared["Shared Resources"]
        SCONF["Config & Database Session"]
        SMODEL["Models & Schemas"]
        SREDIS["Redis & Locks"]
    end

    Redis["Redis"]
    MySQL["MySQL"]

    UI -->|"HTTP"| FAPI
    WS <-->|"WebSocket"| FAPI

    FAPI --> FCOORD
    FAPI --> FREPO
    FAPI --> FBREPO

    FCOORD -->|"HTTP /internal/*"| UAPI

    UAPI --> UREPO
    UAPI --> UBREPO

    FREPO --> MySQL
    FBREPO --> MySQL
    UREPO --> MySQL
    UBREPO --> MySQL

    FCOORD --> Redis
    FAPI --> Redis
    UAPI --> Redis

    Field -.-> Shared
    Utility -.-> Shared

