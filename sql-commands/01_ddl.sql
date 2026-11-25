-- =====================================================
-- Smart Office Seat & Co-working Space Allocation System
-- 01_ddl.sql | MySQL 8.0+ | InnoDB (needed for transactions/locking)
-- =====================================================
DROP DATABASE IF EXISTS smart_office;
CREATE DATABASE smart_office;
USE smart_office;

-- 1. DEPARTMENT
CREATE TABLE department (
    dept_id    INT AUTO_INCREMENT PRIMARY KEY,
    dept_name  VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- 2. EMPLOYEE (BR1, BR14)
CREATE TABLE employee (
    emp_id   INT AUTO_INCREMENT PRIMARY KEY,
    name     VARCHAR(80)  NOT NULL,
    email    VARCHAR(100) NOT NULL UNIQUE,
    phone    VARCHAR(15),
    role     VARCHAR(20)  NOT NULL DEFAULT 'Employee',
    dept_id  INT NOT NULL,
    CONSTRAINT chk_emp_role CHECK (role IN ('Employee','Facility Manager','Admin','Security')),
    CONSTRAINT fk_emp_dept FOREIGN KEY (dept_id) REFERENCES department(dept_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 3. OFFICE
CREATE TABLE office (
    office_id    INT AUTO_INCREMENT PRIMARY KEY,
    office_name  VARCHAR(80) NOT NULL,
    city         VARCHAR(50) NOT NULL,
    address      VARCHAR(150)
) ENGINE=InnoDB;

-- 4. FLOOR (BR2)
CREATE TABLE floor (
    floor_id   INT AUTO_INCREMENT PRIMARY KEY,
    floor_no   INT NOT NULL,
    office_id  INT NOT NULL,
    CONSTRAINT uq_floor UNIQUE (office_id, floor_no),
    CONSTRAINT fk_floor_office FOREIGN KEY (office_id) REFERENCES office(office_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 5. ZONE
CREATE TABLE zone (
    zone_id    INT AUTO_INCREMENT PRIMARY KEY,
    zone_name  VARCHAR(50) NOT NULL,
    floor_id   INT NOT NULL,
    CONSTRAINT uq_zone UNIQUE (floor_id, zone_name),
    CONSTRAINT fk_zone_floor FOREIGN KEY (floor_id) REFERENCES floor(floor_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 6. RESOURCE (parent of DESK and ROOM) (BR3, BR7)
CREATE TABLE resource (
    resource_id    INT AUTO_INCREMENT PRIMARY KEY,
    resource_code  VARCHAR(20) NOT NULL UNIQUE,
    resource_type  VARCHAR(10) NOT NULL,
    status         VARCHAR(15) NOT NULL DEFAULT 'Active',
    zone_id        INT NOT NULL,
    CONSTRAINT chk_res_type   CHECK (resource_type IN ('Desk','Room')),
    CONSTRAINT chk_res_status CHECK (status IN ('Active','Maintenance','Inactive')),
    CONSTRAINT fk_res_zone FOREIGN KEY (zone_id) REFERENCES zone(zone_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 7. DESK (subtype)
CREATE TABLE desk (
    resource_id  INT PRIMARY KEY,
    desk_number  VARCHAR(10) NOT NULL,
    desk_type    VARCHAR(15) NOT NULL DEFAULT 'Standard',
    CONSTRAINT chk_desk_type CHECK (desk_type IN ('Standard','Standing','Quiet')),
    CONSTRAINT fk_desk_res FOREIGN KEY (resource_id) REFERENCES resource(resource_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- 8. ROOM (subtype) (BR6)
CREATE TABLE room (
    resource_id  INT PRIMARY KEY,
    room_name    VARCHAR(50) NOT NULL,
    capacity     INT NOT NULL,
    CONSTRAINT chk_room_cap CHECK (capacity BETWEEN 1 AND 100),
    CONSTRAINT fk_room_res FOREIGN KEY (resource_id) REFERENCES resource(resource_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- 9. AMENITY
CREATE TABLE amenity (
    amenity_id    INT AUTO_INCREMENT PRIMARY KEY,
    amenity_name  VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- 10. RESOURCE_AMENITY (M:N link)
CREATE TABLE resource_amenity (
    resource_id  INT NOT NULL,
    amenity_id   INT NOT NULL,
    PRIMARY KEY (resource_id, amenity_id),
    CONSTRAINT fk_ra_res FOREIGN KEY (resource_id) REFERENCES resource(resource_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ra_amen FOREIGN KEY (amenity_id) REFERENCES amenity(amenity_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- 11. BOOKING (BR4, BR8, BR13)
CREATE TABLE booking (
    booking_id    INT AUTO_INCREMENT PRIMARY KEY,
    emp_id        INT NOT NULL,
    resource_id   INT NOT NULL,
    booking_date  DATE NOT NULL,
    start_time    TIME NOT NULL,
    end_time      TIME NOT NULL,
    attendees     INT NOT NULL DEFAULT 1,
    status        VARCHAR(15) NOT NULL DEFAULT 'Confirmed',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_book_time      CHECK (end_time > start_time),
    CONSTRAINT chk_book_attendees CHECK (attendees >= 1),
    CONSTRAINT chk_book_status    CHECK (status IN ('Confirmed','Cancelled','Completed','No-Show')),
    CONSTRAINT fk_book_emp FOREIGN KEY (emp_id) REFERENCES employee(emp_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_book_res FOREIGN KEY (resource_id) REFERENCES resource(resource_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 12. CANCELLATION (BR9)
CREATE TABLE cancellation (
    cancel_id     INT AUTO_INCREMENT PRIMARY KEY,
    booking_id    INT NOT NULL UNIQUE,
    cancelled_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason        VARCHAR(200),
    CONSTRAINT fk_cancel_book FOREIGN KEY (booking_id) REFERENCES booking(booking_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 13. ACCESS_LOG (BR10)
CREATE TABLE access_log (
    log_id          INT AUTO_INCREMENT PRIMARY KEY,
    booking_id      INT NOT NULL UNIQUE,
    check_in_time   DATETIME NOT NULL,
    check_out_time  DATETIME NULL,
    CONSTRAINT chk_log_time CHECK (check_out_time IS NULL OR check_out_time > check_in_time),
    CONSTRAINT fk_log_book FOREIGN KEY (booking_id) REFERENCES booking(booking_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;