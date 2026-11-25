-- =====================================================
-- 03_queries_views_indexes.sql  | run AFTER 01_ddl.sql and 02_data.sql
-- Utilization = booked hours (Confirmed + Completed) / available hours
-- Available hours = 10 hours/day (9:00-19:00) x 20 working days (Nov 2-27) = 200 hours
-- =====================================================
USE smart_office;

-- ---------- A. JOINS ----------

-- Q1. INNER JOIN: booking details across 6 tables (first 15 rows)
SELECT b.booking_id, e.name AS employee, d.dept_name, r.resource_code, r.resource_type,
       z.zone_name, f.floor_no, o.office_name, b.booking_date, b.start_time, b.end_time, b.status
FROM booking b
JOIN employee   e ON e.emp_id      = b.emp_id
JOIN department d ON d.dept_id     = e.dept_id
JOIN resource   r ON r.resource_id = b.resource_id
JOIN zone       z ON z.zone_id     = r.zone_id
JOIN floor      f ON f.floor_id    = z.floor_id
JOIN office     o ON o.office_id   = f.office_id
ORDER BY b.booking_date, b.start_time
LIMIT 15;

-- Q2. LEFT OUTER JOIN: resources that were never booked
SELECT r.resource_code, r.resource_type, r.status
FROM resource r
LEFT JOIN booking b ON b.resource_id = r.resource_id
WHERE b.booking_id IS NULL;

-- Q3. SELF JOIN: pairs of colleagues in the same department (first 10)
SELECT e1.name AS employee_1, e2.name AS employee_2, d.dept_name
FROM employee e1
JOIN employee e2   ON e1.dept_id = e2.dept_id AND e1.emp_id < e2.emp_id
JOIN department d  ON d.dept_id = e1.dept_id
ORDER BY d.dept_name, e1.emp_id
LIMIT 10;

-- Q4. SELF JOIN on booking: detect overlapping active bookings (BR5). Expected: 0 rows
SELECT a.booking_id AS booking_a, b.booking_id AS booking_b, a.resource_id, a.booking_date
FROM booking a
JOIN booking b ON a.resource_id = b.resource_id
              AND a.booking_date = b.booking_date
              AND a.booking_id < b.booking_id
              AND a.start_time < b.end_time AND a.end_time > b.start_time
WHERE a.status <> 'Cancelled' AND b.status <> 'Cancelled';

-- Q5. CROSS JOIN: every zone x every day of one week, with booking counts (zeros included)
SELECT z.zone_name, f.floor_no, o.city, d.day, COUNT(b.booking_id) AS bookings
FROM zone z
JOIN floor f  ON f.floor_id  = z.floor_id
JOIN office o ON o.office_id = f.office_id
CROSS JOIN (SELECT '2026-11-16' AS day UNION ALL SELECT '2026-11-17' UNION ALL
            SELECT '2026-11-18' UNION ALL SELECT '2026-11-19' UNION ALL SELECT '2026-11-20') d
LEFT JOIN resource r ON r.zone_id = z.zone_id
LEFT JOIN booking b  ON b.resource_id = r.resource_id AND b.booking_date = d.day
                    AND b.status <> 'Cancelled'
GROUP BY z.zone_id, z.zone_name, f.floor_no, o.city, d.day
ORDER BY o.city, f.floor_no, z.zone_name, d.day
LIMIT 20;

-- ---------- B. SUBQUERIES ----------

-- Q6. Rooms with capacity >= 20 that are FREE for 11:00-13:00 on 2 Nov 2026 (NOT EXISTS)
SELECT r.resource_code, rm.room_name, rm.capacity, z.zone_name
FROM resource r
JOIN room rm ON rm.resource_id = r.resource_id
JOIN zone z  ON z.zone_id = r.zone_id
WHERE rm.capacity >= 20
  AND r.status = 'Active'
  AND NOT EXISTS (SELECT 1 FROM booking b
                  WHERE b.resource_id = r.resource_id
                    AND b.booking_date = '2026-11-02'
                    AND b.status <> 'Cancelled'
                    AND b.start_time < '13:00:00'
                    AND b.end_time   > '11:00:00');

-- Q7. Scalar subquery: employees with more bookings than the average employee
SELECT e.name, COUNT(*) AS total_bookings
FROM employee e
JOIN booking b ON b.emp_id = e.emp_id
WHERE b.status <> 'Cancelled'
GROUP BY e.emp_id, e.name
HAVING COUNT(*) > (SELECT COUNT(*) / COUNT(DISTINCT emp_id) FROM booking WHERE status <> 'Cancelled')
ORDER BY total_bookings DESC;

-- Q8. Correlated subquery: each employee's latest booking date
SELECT e.name,
       (SELECT MAX(b.booking_date) FROM booking b WHERE b.emp_id = e.emp_id) AS last_booking
FROM employee e
ORDER BY last_booking DESC
LIMIT 10;

-- Q9. IN subquery: employees who booked a large room (capacity >= 20)
SELECT DISTINCT e.name
FROM employee e
WHERE e.emp_id IN (SELECT b.emp_id FROM booking b
                   JOIN room rm ON rm.resource_id = b.resource_id
                   WHERE rm.capacity >= 20);

-- Q10. Employees who reserved but never checked in (past bookings, no access_log row)
SELECT e.name, d.dept_name, COUNT(*) AS missed_checkins
FROM booking b
JOIN employee e   ON e.emp_id = b.emp_id
JOIN department d ON d.dept_id = e.dept_id
LEFT JOIN access_log l ON l.booking_id = b.booking_id
WHERE b.status <> 'Cancelled'
  AND b.booking_date < '2026-11-15'
  AND l.log_id IS NULL
GROUP BY e.emp_id, e.name, d.dept_name
ORDER BY missed_checkins DESC;

-- ---------- C. SET OPERATIONS (UNION / INTERSECT / EXCEPT need MySQL 8.0.31+) ----------

-- Q11a. UNION: employees who booked a desk OR a room
SELECT e.name FROM employee e JOIN booking b ON b.emp_id = e.emp_id
  JOIN resource r ON r.resource_id = b.resource_id WHERE r.resource_type = 'Desk'
UNION
SELECT e.name FROM employee e JOIN booking b ON b.emp_id = e.emp_id
  JOIN resource r ON r.resource_id = b.resource_id WHERE r.resource_type = 'Room';

-- Q11b. INTERSECT: employees who booked BOTH a desk and a room
SELECT b.emp_id FROM booking b JOIN resource r ON r.resource_id = b.resource_id WHERE r.resource_type = 'Desk'
INTERSECT
SELECT b.emp_id FROM booking b JOIN resource r ON r.resource_id = b.resource_id WHERE r.resource_type = 'Room';

-- Q11c. EXCEPT: employees who booked desks but NEVER a room
SELECT b.emp_id FROM booking b JOIN resource r ON r.resource_id = b.resource_id WHERE r.resource_type = 'Desk'
EXCEPT
SELECT b.emp_id FROM booking b JOIN resource r ON r.resource_id = b.resource_id WHERE r.resource_type = 'Room';
-- (older MySQL fallback for Q11b/Q11c: use  WHERE emp_id IN (...)  /  WHERE emp_id NOT IN (...))

-- ---------- D. AGGREGATES, GROUP BY, HAVING ----------

-- Q12. Rooms that have BOTH a Projector and Video Conferencing (M:N relationship)
SELECT r.resource_code, rm.room_name, rm.capacity
FROM resource r
JOIN room rm ON rm.resource_id = r.resource_id
JOIN resource_amenity ra ON ra.resource_id = r.resource_id
JOIN amenity a ON a.amenity_id = ra.amenity_id
WHERE a.amenity_name IN ('Projector', 'Video Conferencing')
GROUP BY r.resource_id, r.resource_code, rm.room_name, rm.capacity
HAVING COUNT(DISTINCT a.amenity_name) = 2;

-- Q13. Cancellation analysis: count and average notice (hours before start) by reason
SELECT c.reason, COUNT(*) AS cancellations,
       ROUND(AVG(TIMESTAMPDIFF(HOUR, c.cancelled_at, TIMESTAMP(b.booking_date, b.start_time))), 1) AS avg_notice_hours
FROM cancellation c
JOIN booking b ON b.booking_id = c.booking_id
GROUP BY c.reason
ORDER BY cancellations DESC;

-- ---------- E. CTEs ----------

-- Q14. CTE: daily and weekly occupancy (booked hours per day, then rolled up per week)
WITH daily AS (
    SELECT booking_date,
           COUNT(*) AS bookings,
           ROUND(SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)) / 60, 1) AS booked_hours
    FROM booking
    WHERE status IN ('Confirmed', 'Completed')
    GROUP BY booking_date
)
SELECT YEARWEEK(booking_date, 1) AS year_week,
       MIN(booking_date) AS week_start,
       SUM(bookings)     AS weekly_bookings,
       SUM(booked_hours) AS weekly_hours,
       ROUND(AVG(booked_hours), 1) AS avg_daily_hours
FROM daily
GROUP BY YEARWEEK(booking_date, 1)
ORDER BY year_week;

-- Q15. Recursive CTE: peak booking hours (how many bookings are active in each hour)
WITH RECURSIVE hours AS (
    SELECT 9 AS hr
    UNION ALL
    SELECT hr + 1 FROM hours WHERE hr < 18
)
SELECT CONCAT(LPAD(h.hr, 2, '0'), ':00') AS hour_slot,
       COUNT(b.booking_id) AS active_bookings
FROM hours h
LEFT JOIN booking b ON b.status IN ('Confirmed', 'Completed')
                   AND HOUR(b.start_time) <= h.hr
                   AND b.end_time > MAKETIME(h.hr, 0, 0)
GROUP BY h.hr
ORDER BY active_bookings DESC;

-- ---------- F. WINDOW FUNCTIONS ----------

-- Q16. RANK zones by utilization %
WITH zone_util AS (
    SELECT z.zone_id, z.zone_name, o.city, f.floor_no,
           COUNT(DISTINCT r.resource_id) AS resources,
           ROUND(COALESCE(SUM(TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time)), 0) / 60, 1) AS booked_hours
    FROM zone z
    JOIN floor f  ON f.floor_id  = z.floor_id
    JOIN office o ON o.office_id = f.office_id
    JOIN resource r ON r.zone_id = z.zone_id AND r.status = 'Active'
    LEFT JOIN booking b ON b.resource_id = r.resource_id AND b.status IN ('Confirmed', 'Completed')
    GROUP BY z.zone_id, z.zone_name, o.city, f.floor_no
)
SELECT RANK() OVER (ORDER BY booked_hours / (resources * 200) DESC) AS util_rank,
       city, floor_no, zone_name, resources, booked_hours,
       ROUND(100 * booked_hours / (resources * 200), 1) AS utilization_pct
FROM zone_util
ORDER BY util_rank;

-- Q17. DENSE_RANK: top 2 employees by booked hours inside each department
WITH emp_hours AS (
    SELECT e.emp_id, e.name, d.dept_name,
           ROUND(SUM(TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time)) / 60, 1) AS hours
    FROM booking b
    JOIN employee e   ON e.emp_id = b.emp_id
    JOIN department d ON d.dept_id = e.dept_id
    WHERE b.status IN ('Confirmed', 'Completed')
    GROUP BY e.emp_id, e.name, d.dept_name
), ranked AS (
    SELECT *, DENSE_RANK() OVER (PARTITION BY dept_name ORDER BY hours DESC) AS dept_rank
    FROM emp_hours
)
SELECT dept_name, dept_rank, name, hours
FROM ranked
WHERE dept_rank <= 2
ORDER BY dept_name, dept_rank;

-- Q18. Running total and day-over-day change (SUM OVER, LAG)
WITH daily AS (
    SELECT booking_date, COUNT(*) AS bookings
    FROM booking WHERE status <> 'Cancelled'
    GROUP BY booking_date
)
SELECT booking_date, bookings,
       SUM(bookings) OVER (ORDER BY booking_date) AS running_total,
       bookings - LAG(bookings) OVER (ORDER BY booking_date) AS change_vs_prev_day
FROM daily
ORDER BY booking_date;

-- Q19. Resources with utilization BELOW the average (CTE + subquery)
WITH res_util AS (
    SELECT r.resource_id, r.resource_code, r.resource_type,
           ROUND(100 * COALESCE(SUM(TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time)), 0) / 60 / 200, 1) AS util_pct
    FROM resource r
    LEFT JOIN booking b ON b.resource_id = r.resource_id AND b.status IN ('Confirmed', 'Completed')
    WHERE r.status = 'Active'
    GROUP BY r.resource_id, r.resource_code, r.resource_type
)
SELECT resource_code, resource_type, util_pct,
       (SELECT ROUND(AVG(util_pct), 1) FROM res_util) AS average_pct
FROM res_util
WHERE util_pct < (SELECT AVG(util_pct) FROM res_util)
ORDER BY util_pct;

-- =====================================================
-- G. VIEWS
-- =====================================================

-- V1. Current availability: active resources not booked right now
CREATE OR REPLACE VIEW v_current_availability AS
SELECT r.resource_id, r.resource_code, r.resource_type, z.zone_name, f.floor_no, o.city
FROM resource r
JOIN zone z   ON z.zone_id   = r.zone_id
JOIN floor f  ON f.floor_id  = z.floor_id
JOIN office o ON o.office_id = f.office_id
WHERE r.status = 'Active'
  AND NOT EXISTS (SELECT 1 FROM booking b
                  WHERE b.resource_id = r.resource_id
                    AND b.booking_date = CURDATE()
                    AND b.status IN ('Confirmed', 'Completed')
                    AND CURTIME() >= b.start_time AND CURTIME() < b.end_time);

-- V2. Booking details (readable report view)
CREATE OR REPLACE VIEW v_booking_details AS
SELECT b.booking_id, e.name AS employee, d.dept_name, r.resource_code, r.resource_type,
       z.zone_name, o.city, b.booking_date, b.start_time, b.end_time, b.attendees, b.status
FROM booking b
JOIN employee e   ON e.emp_id = b.emp_id
JOIN department d ON d.dept_id = e.dept_id
JOIN resource r   ON r.resource_id = b.resource_id
JOIN zone z       ON z.zone_id = r.zone_id
JOIN floor f      ON f.floor_id = z.floor_id
JOIN office o     ON o.office_id = f.office_id;

-- V3. Utilization per resource
CREATE OR REPLACE VIEW v_resource_utilization AS
SELECT r.resource_id, r.resource_code, r.resource_type,
       ROUND(COALESCE(SUM(TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time)), 0) / 60, 1) AS booked_hours,
       ROUND(100 * COALESCE(SUM(TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time)), 0) / 60 / 200, 1) AS util_pct
FROM resource r
LEFT JOIN booking b ON b.resource_id = r.resource_id AND b.status IN ('Confirmed', 'Completed')
WHERE r.status = 'Active'
GROUP BY r.resource_id, r.resource_code, r.resource_type;

-- Using the views
SELECT * FROM v_current_availability LIMIT 10;
SELECT * FROM v_booking_details WHERE booking_date = '2026-11-18' ORDER BY start_time;
SELECT * FROM v_resource_utilization ORDER BY util_pct DESC LIMIT 10;

-- =====================================================
-- H. INDEXES + EXPLAIN
-- =====================================================

-- Step 1: look at the plan BEFORE adding indexes
EXPLAIN SELECT booking_id FROM booking
WHERE resource_id = 2 AND booking_date = '2026-11-18' AND status <> 'Cancelled'
  AND start_time < '13:00:00' AND end_time > '11:00:00';

EXPLAIN SELECT booking_date, COUNT(*) FROM booking
WHERE booking_date BETWEEN '2026-11-16' AND '2026-11-20' AND status = 'Confirmed'
GROUP BY booking_date;

-- Step 2: create the indexes
-- Index 1: speeds up the overlap check (BR5) - the most frequent query in the system
CREATE INDEX idx_booking_overlap ON booking (resource_id, booking_date, start_time, end_time);
-- Index 2: speeds up daily/weekly reports and availability searches
CREATE INDEX idx_booking_date_status ON booking (booking_date, status);

-- Step 3: look at the plans AFTER (same two statements)
EXPLAIN SELECT booking_id FROM booking
WHERE resource_id = 2 AND booking_date = '2026-11-18' AND status <> 'Cancelled'
  AND start_time < '13:00:00' AND end_time > '11:00:00';

EXPLAIN SELECT booking_date, COUNT(*) FROM booking
WHERE booking_date BETWEEN '2026-11-16' AND '2026-11-20' AND status = 'Confirmed'
GROUP BY booking_date;

SHOW INDEX FROM booking;
