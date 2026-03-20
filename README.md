# DS-PracticeCourt – Distributed Sports Field Booking System

## Vision
The goal of this project is to design and implement **DS-PracticeCourt**, a distributed web-based system for booking sports facilities (such as soccer, padel, basketball) and related services.

Users will be able to:
- Browse available sports facilities
- Check and select available time slots
- Reserve a field for a specific time
- Book additional services (e.g., heating, lighting, equipment rental)

The system follows a **distributed client–server architecture**:
- Users interact through a web client
- Multiple backend nodes cooperate to manage reservations and services

---

## System Architecture

The system is composed of multiple backend nodes:

- **Field Nodes**
    - Manage sports facilities
    - Handle reservations

- **Utility Nodes**
    - Manage additional services (lighting, heating, equipment rental)

---

## Key Challenges

- Managing **concurrent booking requests**
- Preventing **double bookings**
- Supporting **temporary reservations**
- Coordinating distributed services

---

## Key Functionalities

### User Access and Field Browsing
Users can:
- View available sports facilities
- Check available time slots

### Reservation System
Users can:
- Reserve a field for a specific time slot
- Select additional services

### Concurrent Booking Management
- Use of **distributed locks**
- Ensures only one reservation succeeds per slot

### Temporary Slot Locking
- Slots are temporarily reserved when selected
- Timeout releases the slot if not confirmed

### Real-Time Updates
- Clients receive updates via **WebSockets**
- Availability is updated instantly

### Distributed Architecture
- Multiple nodes simulate:
    - Different facility managers
    - Service providers

---

## Learning Goals

This project explores key Distributed Systems concepts:

- **Concurrency Management**
    - Handling simultaneous booking requests safely

- **Distributed Coordination**
    - Synchronizing multiple backend nodes

- **Scalability**
    - Supporting multiple users and operations

- **Fault Tolerance**
    - Handling node failures during transactions

- **Real-Time Communication**
    - Keeping clients synchronized

---

## Technologies

- **Backend:** Python + FastAPI
- **Frontend:** HTML / JavaScript (or React)
- **Database:** MySQL
- **Coordination & Caching:** Redis (distributed locking)
- **Communication:** WebSockets
- **Containerization:** Docker / Docker Compose

---

## Deliverables

- Distributed backend system for field reservations
- Web interface for browsing and booking
- Dockerized environment simulating multiple nodes
- Test scenario for concurrent booking handling
- Final technical report (architecture + implementation)

---

## Usage Scenarios

### Concurrent Reservation Attempt
Two users attempt to book the same field and time slot:
- Distributed locking ensures only one succeeds

### Temporary Reservation with Timeout
- Slot is temporarily locked
- If not confirmed, it becomes available again

### Atomic Field and Service Booking
- Booking includes both field and service (e.g., heating)
- Uses **Two-Phase Commit (2PC)**
- If one operation fails → entire booking is rolled back

### Real-Time Updates
- All connected clients receive availability updates instantly

### Node Failure Scenario
- System detects node failure
- Other nodes continue processing when possible

---

## Group Members

- **Federico Brighi**  
  federico.brighi2@studio.unibo.it  
  *(Individual project)*