CREATE DATABASE IF NOT EXISTS practicecourt
       CHARACTER SET utf8mb4
       COLLATE utf8mb4_unicode_ci;

USE practicecourt;

-- SPORT FIELDS

CREATE TABLE IF NOT EXISTS fields (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    sport_type ENUM('football', 'tennis', 'basketball') NOT NULL,
    location VARCHAR(200) NOT NULL,
    price_per_hour DECIMAL(6,2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

-- UTILITY SERVICES

CREATE TABLE IF NOT EXISTS utilities (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    utility_type ENUM('room', 'heating', 'lighting', 'equipment_rental') NOT NULL,
    price_per_hour DECIMAL(6,2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id)
);

-- FIELD BOOKING

CREATE TABLE IF NOT EXISTS field_bookings (
    id INT NOT NULL AUTO_INCREMENT,
    field_id INT NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    status ENUM('pending', 'confirmed', 'cancelled', 'failed') NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (field_id) REFERENCES fields(id),
    INDEX idx_field_time (field_id, start_time, end_time)
);

-- UTILITY BOOKING

CREATE TABLE IF NOT EXISTS utility_bookings (
    id INT NOT NULL AUTO_INCREMENT,
    booking_id INT NOT NULL,
    utility_id INT NOT NULL,
    status ENUM('pending', 'confirmed', 'cancelled', 'failed') NOT NULL DEFAULT 'pending',
    PRIMARY KEY (id),
    FOREIGN KEY (utility_id) REFERENCES utilities(id),
    INDEX idx_booking (booking_id)
);

-- STARTING VALUES

INSERT INTO fields (name, sport_type, location, price_per_hour) VALUES
    ('Field A', 'football', 'Zone F', 10.00),
    ('Court B', 'tennis', 'Zone T', 15.00),
    ('Court C', 'basketball', 'Zone B', 8.00);

INSERT INTO utilities (name, utility_type, price_per_hour) VALUES
    ('Changing Room', 'room', 9.00),
    ('Field Heating', 'heating', 10.00),
    ('Nocturnal Lighting', 'lighting', 7.00),
    ('Tennis Racket Rental', 'equipment_rental', 8.00);