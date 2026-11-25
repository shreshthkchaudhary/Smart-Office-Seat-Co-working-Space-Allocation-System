-- =====================================================
-- 05_transactions_concurrency_demo.sql
-- DO NOT press "Execute All". Run ONE statement at a time (Ctrl+Enter) and screenshot.
-- Uses dates 2026-11-18 (D-102 demo), 2026-11-25 (concurrency) and 2026-11-30 (transactions),
-- so your earlier data is not disturbed.
-- Resource ids: D-102 = 2, D-103 = 3, R-203 = 43 (capacity 8), D-107 = 7 (maintenance)
-- =====================================================
USE smart_office;

-- ---------- PART 1: PROCEDURE TESTS ----------

-- 1a. The brief's example: D-102 is booked 10:00-12:00 on 18 Nov.
--     11:00-13:00 must be REJECTED
CALL sp_book_resource(1, 2, '2026-11-18', '11:00', '13:00', 1, @id, @msg);
SELECT @id AS booking_id, @msg AS result;

--     12:00-14:00 must be ACCEPTED (back-to-back is allowed)
CALL sp_book_resource(1, 2, '2026-11-18', '12:00', '14:00', 1, @id, @msg);
SELECT @id AS booking_id, @msg AS result;

-- 1b. Business-rule failures (all REJECTED by Trigger 1)
CALL sp_book_resource(1, 43, '2026-11-30', '10:00', '12:00', 15, @id, @msg); SELECT @id, @msg;  -- BR6: 15 people in a room for 8
CALL sp_book_resource(1, 7,  '2026-11-30', '10:00', '12:00', 1,  @id, @msg); SELECT @id, @msg;  -- BR7: desk under maintenance
CALL sp_book_resource(1, 3,  '2026-11-30', '09:00', '19:30', 1,  @id, @msg); SELECT @id, @msg;  -- BR12: desk > 9 hours

-- ---------- PART 2: THREE TRANSACTION SCENARIOS ----------

-- Scenario 1: successful transaction (COMMIT) - booking through the procedure
CALL sp_book_resource(2, 3, '2026-11-30', '09:00', '13:00', 1, @id, @msg);
SELECT @id AS booking_id, @msg AS result;
SELECT * FROM booking WHERE booking_id = @id;

-- Scenario 2: failed transaction (ROLLBACK)
START TRANSACTION;
INSERT INTO booking (emp_id, resource_id, booking_date, start_time, end_time)
VALUES (3, 3, '2026-11-30', '14:00', '17:00');
SELECT COUNT(*) AS rows_inside_transaction FROM booking WHERE booking_date = '2026-11-30' AND emp_id = 3;   -- 1
ROLLBACK;
SELECT COUNT(*) AS rows_after_rollback FROM booking WHERE booking_date = '2026-11-30' AND emp_id = 3;       -- 0

-- Scenario 3: SAVEPOINT - book a desk + a room together; the room part fails, the desk part is kept
START TRANSACTION;
INSERT INTO booking (emp_id, resource_id, booking_date, start_time, end_time, attendees)
VALUES (4, 3, '2026-11-30', '14:00', '17:00', 1);                    -- desk D-103: OK
SAVEPOINT after_desk;
INSERT INTO booking (emp_id, resource_id, booking_date, start_time, end_time, attendees)
VALUES (4, 43, '2026-11-30', '14:00', '16:00', 15);                  -- room R-203: FAILS (BR6)
ROLLBACK TO SAVEPOINT after_desk;                                    -- undo only the room part
INSERT INTO booking (emp_id, resource_id, booking_date, start_time, end_time, attendees)
VALUES (4, 43, '2026-11-30', '14:00', '16:00', 6);                   -- retry with 6 people: OK
COMMIT;
SELECT booking_id, emp_id, resource_id, start_time, end_time, attendees, status
FROM booking WHERE booking_date = '2026-11-30' AND emp_id = 4;

-- ---------- PART 3: CANCEL, CHECK-IN, AUDIT (triggers 2 and 3) ----------

-- Cancel the booking from Scenario 1 (use its real booking_id; here we look it up)
SELECT booking_id INTO @b FROM booking WHERE booking_date='2026-11-30' AND resource_id=3 AND emp_id=2 LIMIT 1;
CALL sp_cancel_booking(@b, 10, 'Plan changed', @msg); SELECT @msg;       -- employee 10 is a normal employee, not the owner -> REJECTED
CALL sp_cancel_booking(@b, 2, 'Plan changed', @msg); SELECT @msg;        -- owner -> SUCCESS
CALL sp_cancel_booking(1, 1, 'Too late', @msg);       SELECT @msg;       -- booking 1 is already Completed -> REJECTED (BR9)

SELECT * FROM booking_audit ORDER BY audit_id DESC;                      -- audit record created by Trigger 2

-- Check-in window (BR10) on the D-102 booking of 18 Nov 10:00 (booking found by code)
SELECT b.booking_id INTO @cb FROM booking b WHERE b.resource_id = 2 AND b.booking_date = '2026-11-18' AND b.start_time = '10:00:00';
CALL sp_check_in(@cb, '2026-11-18 09:00:00', @msg); SELECT @msg;         -- 60 min early -> REJECTED
CALL sp_check_in(@cb, '2026-11-18 09:55:00', @msg); SELECT @msg;         -- 5 min early  -> SUCCESS
CALL sp_check_in(@cb, '2026-11-18 09:56:00', @msg); SELECT @msg;         -- second time  -> REJECTED (duplicate)

-- Functions
SELECT resource_code, fn_utilization_pct(resource_id) AS util_pct FROM resource WHERE resource_type='Room';
SELECT resource_code, fn_is_available(resource_id, '2026-11-18', '11:00', '13:00') AS free_11_to_13
FROM resource WHERE resource_id IN (2, 3, 7, 41);

-- ---------- PART 4: CONCURRENCY - TWO SESSIONS ----------
-- Open TWO query tabs in Workbench (File > New Query Tab). Tab 1 = Session A, Tab 2 = Session B.
-- Both tabs need:  USE smart_office;
-- Goal: A and B both try to book Desk D-102 on 25 Nov: A wants 10:00-12:00, B wants 11:00-13:00.

-- === DEMO 1: WITHOUT protection (shows the problem: double booking) ===
-- Run the steps in this exact order, switching tabs as shown:
-- [A] START TRANSACTION;
-- [A] SELECT COUNT(*) AS conflicts FROM booking WHERE resource_id=2 AND booking_date='2026-11-25' AND status<>'Cancelled' AND start_time<'12:00' AND end_time>'10:00';   -- 0
-- [B] START TRANSACTION;
-- [B] SELECT COUNT(*) AS conflicts FROM booking WHERE resource_id=2 AND booking_date='2026-11-25' AND status<>'Cancelled' AND start_time<'13:00' AND end_time>'11:00';   -- 0 (A has not committed yet)
-- [A] INSERT INTO booking (emp_id,resource_id,booking_date,start_time,end_time) VALUES (1,2,'2026-11-25','10:00','12:00');
-- [A] COMMIT;
-- [B] INSERT INTO booking (emp_id,resource_id,booking_date,start_time,end_time) VALUES (2,2,'2026-11-25','11:00','13:00');
-- [B] COMMIT;
-- Either tab: run the overlap query (Q4 from file 03). It now shows a DOUBLE BOOKING. Then clean up:
-- DELETE FROM booking WHERE resource_id = 2 AND booking_date = '2026-11-25';

-- === DEMO 2: WITH locking (the fix) ===
-- [A] START TRANSACTION;
-- [A] SELECT status FROM resource WHERE resource_id = 2 FOR UPDATE;           -- A takes the lock
-- [A] INSERT INTO booking (emp_id,resource_id,booking_date,start_time,end_time) VALUES (1,2,'2026-11-25','10:00','12:00');
--     (do NOT commit yet)
-- [B] CALL sp_book_resource(2, 2, '2026-11-25', '11:00', '13:00', 1, @id, @msg);
--     -> B shows "Running..." and WAITS. Take a screenshot of this!
-- [A] COMMIT;                                                                  -- lock released
-- [B] now finishes. Run:  SELECT @id, @msg;
--     -> REJECTED: time slot overlaps an existing booking
-- [B] CALL sp_book_resource(2, 2, '2026-11-25', '12:00', '14:00', 1, @id, @msg); SELECT @id, @msg;   -- SUCCESS
-- Check: SELECT * FROM booking WHERE resource_id=2 AND booking_date='2026-11-25';
-- Clean up: DELETE FROM booking WHERE resource_id = 2 AND booking_date = '2026-11-25';

-- === DEMO 3: DEADLOCK (opposite lock order) ===
-- [A] START TRANSACTION;
-- [A] SELECT * FROM resource WHERE resource_id = 2 FOR UPDATE;
-- [B] START TRANSACTION;
-- [B] SELECT * FROM resource WHERE resource_id = 3 FOR UPDATE;
-- [A] SELECT * FROM resource WHERE resource_id = 3 FOR UPDATE;   -- A waits for B
-- [B] SELECT * FROM resource WHERE resource_id = 2 FOR UPDATE;   -- B waits for A  => DEADLOCK
--     MySQL kills one session: ERROR 1213 Deadlock found when trying to get lock; try restarting transaction
-- [both] ROLLBACK;
-- FIX: always lock resources in ascending resource_id order (2 first, then 3) - then no cycle can form.
-- Look at it with:  SHOW ENGINE INNODB STATUS;   (section "LATEST DETECTED DEADLOCK")

-- ---------- CLEAN UP after all demos (optional) ----------
-- DELETE FROM booking_audit WHERE booking_id IN (SELECT booking_id FROM booking WHERE booking_date IN ('2026-11-30'));
-- DELETE FROM cancellation WHERE booking_id IN (SELECT booking_id FROM booking WHERE booking_date IN ('2026-11-30'));
-- DELETE FROM booking WHERE booking_date = '2026-11-30';
