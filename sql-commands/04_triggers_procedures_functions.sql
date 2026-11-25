-- =====================================================
-- 04_triggers_procedures_functions.sql
-- Run AFTER 01_ddl.sql, 02_data.sql (and 03 if you want the indexes)
-- In Workbench: open the file and press Execute All (lightning bolt)
-- =====================================================
USE smart_office;

-- Audit table used by Trigger 2 (extra table, not part of the 13 core tables)
CREATE TABLE IF NOT EXISTS booking_audit (
    audit_id    INT AUTO_INCREMENT PRIMARY KEY,
    booking_id  INT NOT NULL,
    old_status  VARCHAR(15),
    new_status  VARCHAR(15),
    changed_by  VARCHAR(100),
    changed_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_book FOREIGN KEY (booking_id) REFERENCES booking(booking_id)
) ENGINE=InnoDB;

DELIMITER $$

-- ===================== TRIGGERS =====================

-- Trigger 1: validate every new booking (BR6 capacity, BR7 active resource, BR12 max length)
DROP TRIGGER IF EXISTS trg_booking_bi$$
CREATE TRIGGER trg_booking_bi BEFORE INSERT ON booking
FOR EACH ROW
BEGIN
    DECLARE v_type   VARCHAR(10);
    DECLARE v_status VARCHAR(15);
    DECLARE v_cap    INT;
    DECLARE v_mins   INT;

    SELECT resource_type, status INTO v_type, v_status
    FROM resource WHERE resource_id = NEW.resource_id;

    SET v_mins = TIMESTAMPDIFF(MINUTE, NEW.start_time, NEW.end_time);

    IF v_status <> 'Active' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR7: resource is under maintenance or inactive';
    END IF;

    IF v_type = 'Room' THEN
        SELECT capacity INTO v_cap FROM room WHERE resource_id = NEW.resource_id;
        IF NEW.attendees > v_cap THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR6: attendees exceed room capacity';
        END IF;
        IF v_mins > 240 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR12: a room can be booked for at most 4 hours';
        END IF;
    ELSE
        IF v_mins > 540 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR12: a desk can be booked for at most 9 hours';
        END IF;
    END IF;
END$$

-- Trigger 2: audit every status change of a booking
DROP TRIGGER IF EXISTS trg_booking_au_audit$$
CREATE TRIGGER trg_booking_au_audit AFTER UPDATE ON booking
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        INSERT INTO booking_audit (booking_id, old_status, new_status, changed_by)
        VALUES (NEW.booking_id, OLD.status, NEW.status, USER());
    END IF;
END$$

-- Trigger 3: a cancellation is allowed only for Confirmed bookings, before the start time (BR9)
DROP TRIGGER IF EXISTS trg_cancellation_bi$$
CREATE TRIGGER trg_cancellation_bi BEFORE INSERT ON cancellation
FOR EACH ROW
BEGIN
    DECLARE v_status VARCHAR(15);
    DECLARE v_start  DATETIME;

    SELECT status, TIMESTAMP(booking_date, start_time) INTO v_status, v_start
    FROM booking WHERE booking_id = NEW.booking_id;

    IF v_status <> 'Confirmed' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR9: only Confirmed bookings can be cancelled';
    END IF;
    IF NEW.cancelled_at >= v_start THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR9: a booking cannot be cancelled after its start time';
    END IF;
END$$

-- ===================== FUNCTIONS =====================

-- Function 1: utilization % of one resource (booked hours / 200 available hours)
DROP FUNCTION IF EXISTS fn_utilization_pct$$
CREATE FUNCTION fn_utilization_pct(p_resource_id INT) RETURNS DECIMAL(5,1)
READS SQL DATA
BEGIN
    DECLARE v_minutes INT;
    SELECT COALESCE(SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)), 0) INTO v_minutes
    FROM booking
    WHERE resource_id = p_resource_id AND status IN ('Confirmed', 'Completed');
    RETURN ROUND(100 * v_minutes / 60 / 200, 1);
END$$

-- Function 2: is a resource free for a time interval? (1 = yes, 0 = no)
DROP FUNCTION IF EXISTS fn_is_available$$
CREATE FUNCTION fn_is_available(p_resource_id INT, p_date DATE, p_start TIME, p_end TIME)
RETURNS TINYINT
READS SQL DATA
BEGIN
    DECLARE v_status    VARCHAR(15);
    DECLARE v_conflicts INT;
    SELECT status INTO v_status FROM resource WHERE resource_id = p_resource_id;
    IF v_status IS NULL OR v_status <> 'Active' THEN
        RETURN 0;
    END IF;
    SELECT COUNT(*) INTO v_conflicts FROM booking
    WHERE resource_id = p_resource_id AND booking_date = p_date AND status <> 'Cancelled'
      AND start_time < p_end AND end_time > p_start;
    RETURN IF(v_conflicts = 0, 1, 0);
END$$

-- ===================== PROCEDURES =====================

-- Procedure 1: book a resource safely (BR4, BR5, BR7, BR13)
-- Locks the resource row first, so two people can never get the same slot.
DROP PROCEDURE IF EXISTS sp_book_resource$$
CREATE PROCEDURE sp_book_resource(
    IN  p_emp_id      INT,
    IN  p_resource_id INT,
    IN  p_date        DATE,
    IN  p_start       TIME,
    IN  p_end         TIME,
    IN  p_attendees   INT,
    OUT p_booking_id  INT,
    OUT p_message     VARCHAR(200))
proc: BEGIN
    DECLARE v_status    VARCHAR(15);
    DECLARE v_conflicts INT DEFAULT 0;
    DECLARE v_err       VARCHAR(200);

    -- any error: undo everything and report the reason
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        GET DIAGNOSTICS CONDITION 1 v_err = MESSAGE_TEXT;
        ROLLBACK;
        SET p_booking_id = NULL;
        SET p_message = CONCAT('REJECTED: ', v_err);
    END;

    SET p_booking_id = NULL;
    START TRANSACTION;

    -- Step 1: lock the resource row. Other sessions wanting this resource now WAIT here.
    SELECT status INTO v_status FROM resource WHERE resource_id = p_resource_id FOR UPDATE;
    IF v_status IS NULL THEN
        ROLLBACK;
        SET p_message = 'REJECTED: resource not found';
        LEAVE proc;
    END IF;

    -- Step 2: overlap check (locking read = always sees the latest committed bookings)
    SELECT COUNT(*) INTO v_conflicts FROM booking
    WHERE resource_id = p_resource_id AND booking_date = p_date AND status <> 'Cancelled'
      AND start_time < p_end AND end_time > p_start
    FOR UPDATE;

    IF v_conflicts > 0 THEN
        ROLLBACK;
        SET p_message = 'REJECTED: time slot overlaps an existing booking';
        LEAVE proc;
    END IF;

    -- Step 3: insert (Trigger 1 checks capacity / status / max length)
    INSERT INTO booking (emp_id, resource_id, booking_date, start_time, end_time, attendees)
    VALUES (p_emp_id, p_resource_id, p_date, p_start, p_end, p_attendees);
    SET p_booking_id = LAST_INSERT_ID();

    COMMIT;
    SET p_message = 'SUCCESS: booking confirmed';
END$$

-- Procedure 2: cancel a booking (BR9, BR14). Owner, Admin or Facility Manager only.
DROP PROCEDURE IF EXISTS sp_cancel_booking$$
CREATE PROCEDURE sp_cancel_booking(
    IN  p_booking_id INT,
    IN  p_emp_id     INT,
    IN  p_reason     VARCHAR(200),
    OUT p_message    VARCHAR(200))
proc: BEGIN
    DECLARE v_owner INT;
    DECLARE v_role  VARCHAR(20);
    DECLARE v_err   VARCHAR(200);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        GET DIAGNOSTICS CONDITION 1 v_err = MESSAGE_TEXT;
        ROLLBACK;
        SET p_message = CONCAT('REJECTED: ', v_err);
    END;

    START TRANSACTION;

    SELECT emp_id INTO v_owner FROM booking WHERE booking_id = p_booking_id FOR UPDATE;
    SELECT role   INTO v_role  FROM employee WHERE emp_id = p_emp_id;

    IF v_owner IS NULL THEN
        ROLLBACK;
        SET p_message = 'REJECTED: booking not found';
        LEAVE proc;
    END IF;
    IF v_owner <> p_emp_id AND COALESCE(v_role, '') NOT IN ('Admin', 'Facility Manager') THEN
        ROLLBACK;
        SET p_message = 'REJECTED: you can only cancel your own bookings';
        LEAVE proc;
    END IF;

    INSERT INTO cancellation (booking_id, reason) VALUES (p_booking_id, p_reason);  -- Trigger 3 validates
    UPDATE booking SET status = 'Cancelled' WHERE booking_id = p_booking_id;        -- Trigger 2 audits

    COMMIT;
    SET p_message = 'SUCCESS: booking cancelled';
END$$

-- Procedure 3: check in (BR10): from 15 minutes before to 15 minutes after the start time
-- p_time is optional (NULL = now). It lets you demo with any date.
DROP PROCEDURE IF EXISTS sp_check_in$$
CREATE PROCEDURE sp_check_in(
    IN  p_booking_id INT,
    IN  p_time       DATETIME,
    OUT p_message    VARCHAR(200))
proc: BEGIN
    DECLARE v_status VARCHAR(15);
    DECLARE v_start  DATETIME;
    DECLARE v_time   DATETIME;
    DECLARE v_err    VARCHAR(200);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        GET DIAGNOSTICS CONDITION 1 v_err = MESSAGE_TEXT;
        ROLLBACK;
        SET p_message = CONCAT('REJECTED: ', v_err);
    END;

    SET v_time = COALESCE(p_time, NOW());
    START TRANSACTION;

    SELECT status, TIMESTAMP(booking_date, start_time) INTO v_status, v_start
    FROM booking WHERE booking_id = p_booking_id FOR UPDATE;

    IF v_status IS NULL THEN
        ROLLBACK;
        SET p_message = 'REJECTED: booking not found';
        LEAVE proc;
    END IF;
    IF v_status <> 'Confirmed' THEN
        ROLLBACK;
        SET p_message = 'REJECTED: only Confirmed bookings can be checked in';
        LEAVE proc;
    END IF;
    IF v_time < v_start - INTERVAL 15 MINUTE OR v_time > v_start + INTERVAL 15 MINUTE THEN
        ROLLBACK;
        SET p_message = 'REJECTED: check-in is allowed only 15 minutes before to 15 minutes after the start time';
        LEAVE proc;
    END IF;

    INSERT INTO access_log (booking_id, check_in_time) VALUES (p_booking_id, v_time);  -- UNIQUE blocks double check-in
    COMMIT;
    SET p_message = 'SUCCESS: checked in';
END$$

-- Procedure 4: mark Confirmed bookings as No-Show when nobody checked in within 15 minutes (BR11)
-- WARNING: this changes data. Use p_now to control "the current time".
DROP PROCEDURE IF EXISTS sp_mark_no_shows$$
CREATE PROCEDURE sp_mark_no_shows(IN p_now DATETIME, OUT p_updated INT)
BEGIN
    START TRANSACTION;
    UPDATE booking b
    LEFT JOIN access_log l ON l.booking_id = b.booking_id
    SET b.status = 'No-Show'
    WHERE b.status = 'Confirmed'
      AND l.log_id IS NULL
      AND TIMESTAMP(b.booking_date, b.start_time) + INTERVAL 15 MINUTE < COALESCE(p_now, NOW());
    SET p_updated = ROW_COUNT();
    COMMIT;
END$$

DELIMITER ;
