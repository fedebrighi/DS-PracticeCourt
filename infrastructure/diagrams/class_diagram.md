```mermaid
classDiagram
    class Field {
        +id: int
        +name: str
        +sport_type: str
        +price_per_hour: decimal
        +is_active: bool
    }

    class Utility {
        +id: int
        +name: str
        +utility_type: str
        +price_per_hour: decimal
        +is_active: bool
    }

    class FieldBooking {
        +id: int
        +field_int: int
        +user_id: int
        +start_time: datetime
        +end_time: datetime
        +status: BookingStatus
    }

    class UtilityBooking {
        +id: int
        +booking_id: int
        +utility_id: int
        +status: BookingStatus
    }

    class BookingStatus {
        <<enumeration>>
        PENDING
        CONFIRMED
        CANCELLED
        FAILED
    }

    Field "1" --> "0..*" FieldBooking
    FieldBooking "1" --> "0..*" UtilityBooking
    Utility "1" --> "0..*" UtilityBooking
    FieldBooking --> BookingStatus
    UtilityBooking --> BookingStatus