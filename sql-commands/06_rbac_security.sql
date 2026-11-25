-- ============================================================================
-- 06_rbac_security.sql
-- Task T1: Role-Based Access Control (RBAC), Least Privilege & BR14 View
-- Course: ETCCMS304 | Project 3: Smart Office Seat & Co-working Space Allocation
-- ============================================================================
USE smart_office;

-- ----------------------------------------------------------------------------
-- 1. BR14 VIEW: Employees see ONLY their own bookings
-- Approach:
--   MySQL's USER() function returns the connected client account, e.g.
--   'emp_5@localhost'. We strip '@localhost' using SUBSTRING_INDEX(USER(), '@', 1)
--   to get 'emp_5', then extract the numeric ID (5) after 'emp_'.
--   Because USER() always reflects the logged-in user (unlike CURRENT_USER()),
--   emp_5 only sees rows where b.emp_id = 5.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_my_bookings AS
SELECT b.booking_id,
       b.emp_id,
       e.name          AS employee_name,
       r.resource_code,
       r.resource_type,
       z.zone_name,
       f.floor_no,
       o.city,
       b.booking_date,
       b.start_time,
       b.end_time,
       b.attendees,
       b.status
FROM booking b
JOIN employee e ON e.emp_id = b.emp_id
JOIN resource r ON r.resource_id = b.resource_id
JOIN zone z     ON z.zone_id = r.zone_id
JOIN floor f    ON f.floor_id = z.floor_id
JOIN office o   ON o.office_id = f.office_id
WHERE SUBSTRING_INDEX(USER(), '@', 1) LIKE 'emp\_%'
  AND b.emp_id = CAST(SUBSTRING(SUBSTRING_INDEX(USER(), '@', 1), 5) AS UNSIGNED);

-- Safe employee directory view (hides phone/email if needed, used by app dropdown)
CREATE OR REPLACE VIEW v_employee_directory AS
SELECT e.emp_id, e.name, e.role, d.dept_name
FROM employee e
JOIN department d ON d.dept_id = e.dept_id;

-- ----------------------------------------------------------------------------
-- 2. CREATE 4 ROLES (Least Privilege)
-- ----------------------------------------------------------------------------
CREATE ROLE IF NOT EXISTS 'employee', 'facility_manager', 'admin', 'security';

-- Reset role privileges cleanly before granting
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'employee';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'facility_manager';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'admin';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'security';

-- Role 1: employee (BR14)
--   * NO direct SELECT/INSERT/UPDATE/DELETE on booking, cancellation, access_log, booking_audit.
--   * Can ONLY book, cancel, and check-in via stored procedures (which run with DEFINER privileges).
--   * Can SELECT from safe views and workspace catalog tables.
GRANT SELECT ON smart_office.v_my_bookings          TO 'employee';
GRANT SELECT ON smart_office.v_current_availability TO 'employee';
GRANT SELECT ON smart_office.v_resource_utilization TO 'employee';
GRANT SELECT ON smart_office.v_employee_directory   TO 'employee';
GRANT SELECT ON smart_office.resource               TO 'employee';
GRANT SELECT ON smart_office.desk                   TO 'employee';
GRANT SELECT ON smart_office.room                   TO 'employee';
GRANT SELECT ON smart_office.zone                   TO 'employee';
GRANT SELECT ON smart_office.floor                  TO 'employee';
GRANT SELECT ON smart_office.office                 TO 'employee';
GRANT SELECT ON smart_office.amenity                TO 'employee';
GRANT SELECT ON smart_office.resource_amenity       TO 'employee';
GRANT EXECUTE ON PROCEDURE smart_office.sp_book_resource   TO 'employee';
GRANT EXECUTE ON PROCEDURE smart_office.sp_cancel_booking  TO 'employee';
GRANT EXECUTE ON PROCEDURE smart_office.sp_check_in        TO 'employee';
GRANT EXECUTE ON FUNCTION  smart_office.fn_is_available    TO 'employee';
GRANT EXECUTE ON FUNCTION  smart_office.fn_utilization_pct TO 'employee';

-- Role 2: facility_manager (BR3, BR6, BR7)
--   * Manage workspace inventory: resource, desk, room, amenity, resource_amenity.
--   * Read operational and utilization reports.
--   * Cannot drop tables, alter schema, or delete employee/booking history.
GRANT SELECT, INSERT, UPDATE, DELETE ON smart_office.resource         TO 'facility_manager';
GRANT SELECT, INSERT, UPDATE, DELETE ON smart_office.desk             TO 'facility_manager';
GRANT SELECT, INSERT, UPDATE, DELETE ON smart_office.room             TO 'facility_manager';
GRANT SELECT, INSERT, UPDATE, DELETE ON smart_office.amenity          TO 'facility_manager';
GRANT SELECT, INSERT, UPDATE, DELETE ON smart_office.resource_amenity TO 'facility_manager';
GRANT SELECT ON smart_office.office                 TO 'facility_manager';
GRANT SELECT ON smart_office.floor                  TO 'facility_manager';
GRANT SELECT ON smart_office.zone                   TO 'facility_manager';
GRANT SELECT ON smart_office.department             TO 'facility_manager';
GRANT SELECT ON smart_office.employee               TO 'facility_manager';
GRANT SELECT ON smart_office.v_current_availability TO 'facility_manager';
GRANT SELECT ON smart_office.v_booking_details      TO 'facility_manager';
GRANT SELECT ON smart_office.v_resource_utilization TO 'facility_manager';

-- Role 3: security (BR10)
--   * Read-only access to access_log and v_booking_details for physical/audit checks.
--   * Cannot modify any data or read raw booking/employee tables directly.
GRANT SELECT ON smart_office.access_log        TO 'security';
GRANT SELECT ON smart_office.v_booking_details TO 'security';

-- Role 4: admin
--   * Full privileges on smart_office database.
GRANT ALL PRIVILEGES ON smart_office.* TO 'admin';

-- ----------------------------------------------------------------------------
-- 3. CREATE ONE TEST USER PER ROLE & ASSIGN DEFAULT ROLES
--    Passwords match .env (never commit .env to git).
-- ----------------------------------------------------------------------------
CREATE USER IF NOT EXISTS 'emp_5'@'localhost'        IDENTIFIED BY 'EmpUser@2026!';
CREATE USER IF NOT EXISTS 'fm_user'@'localhost'      IDENTIFIED BY 'FmUser@2026!';
CREATE USER IF NOT EXISTS 'office_admin'@'localhost' IDENTIFIED BY 'AdminUser@2026!';
CREATE USER IF NOT EXISTS 'sec_auditor'@'localhost'  IDENTIFIED BY 'SecUser@2026!';

GRANT 'employee'         TO 'emp_5'@'localhost';
GRANT 'facility_manager' TO 'fm_user'@'localhost';
GRANT 'admin'            TO 'office_admin'@'localhost';
GRANT 'security'         TO 'sec_auditor'@'localhost';

SET DEFAULT ROLE 'employee'         TO 'emp_5'@'localhost';
SET DEFAULT ROLE 'facility_manager' TO 'fm_user'@'localhost';
SET DEFAULT ROLE 'admin'            TO 'office_admin'@'localhost';
SET DEFAULT ROLE 'security'         TO 'sec_auditor'@'localhost';

FLUSH PRIVILEGES;
