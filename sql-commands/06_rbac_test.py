"""
06_rbac_test.py
Task T1: Automated RBAC & Least-Privilege Verification Script.
Connects as each of the 4 role users (using .env, no hard-coded passwords),
runs SHOW GRANTS, one ALLOWED action, one DENIED action, and a REVOKE demo.
Saves the real output to sql-commands/06_rbac_test_output.txt.
"""

import os
import sys
from pathlib import Path
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

HOST = os.getenv("MYSQL_HOST", "localhost")
PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB = os.getenv("MYSQL_DATABASE", "smart_office")

OUT_FILE = Path(__file__).resolve().parent / "06_rbac_test_output.txt"


def connect_as(user: str, password: str):
    return mysql.connector.connect(
        host=HOST, port=PORT, user=user, password=password, database=DB
    )


def run_and_log(lines: list[str], label: str, fn):
    lines.append(f"  [{label}]")
    try:
        result = fn()
        lines.append(f"  RESULT: ALLOWED -> {result}")
    except Error as err:
        lines.append(f"  RESULT: DENIED  -> MySQL Error {err.errno} ({err.sqlstate}): {err.msg}")


def show_grants_for(lines: list[str], conn):
    cur = conn.cursor()
    cur.execute("SHOW GRANTS FOR CURRENT_USER()")
    grants = [row[0] for row in cur.fetchall()]
    cur.close()
    lines.append("  SHOW GRANTS:")
    for g in grants:
        lines.append(f"    {g}")


def main():
    lines = []
    lines.append("=" * 72)
    lines.append("SMART OFFICE RBAC & LEAST-PRIVILEGE VERIFICATION OUTPUT")
    lines.append("=" * 72)

    # 1. EMPLOYEE (emp_5)
    emp_user = os.getenv("MYSQL_EMP_USER", "emp_5")
    emp_pass = os.getenv("MYSQL_EMP_PASSWORD")
    lines.append(f"\n--- ROLE 1: employee (user: {emp_user}) ---")
    conn = connect_as(emp_user, emp_pass)
    show_grants_for(lines, conn)

    def emp_allowed():
        cur = conn.cursor()
        cur.execute("SELECT booking_id, emp_id, resource_code, booking_date, status FROM v_my_bookings LIMIT 3")
        rows = cur.fetchall()
        cur.close()
        return f"v_my_bookings returned {len(rows)} row(s), all for emp_id={rows[0][1] if rows else 'N/A'}"

    def emp_denied():
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO booking (emp_id, resource_id, booking_date, start_time, end_time, attendees) "
            "VALUES (5, 1, '2026-12-01', '10:00:00', '11:00:00', 1)"
        )
        conn.commit()
        cur.close()
        return "Unexpectedly inserted!"

    run_and_log(lines, "ALLOWED: SELECT from BR14 view v_my_bookings", emp_allowed)
    run_and_log(lines, "DENIED : Direct INSERT INTO booking (must use sp_book_resource)", emp_denied)
    conn.close()

    # 2. FACILITY MANAGER (fm_user)
    fm_user = os.getenv("MYSQL_FM_USER", "fm_user")
    fm_pass = os.getenv("MYSQL_FM_PASSWORD")
    lines.append(f"\n--- ROLE 2: facility_manager (user: {fm_user}) ---")
    conn = connect_as(fm_user, fm_pass)
    show_grants_for(lines, conn)

    def fm_allowed():
        cur = conn.cursor()
        cur.execute("SELECT resource_code, util_pct FROM v_resource_utilization ORDER BY util_pct DESC LIMIT 3")
        rows = cur.fetchall()
        cur.close()
        return f"Top utilization rows: {rows}"

    def fm_denied():
        cur = conn.cursor()
        cur.execute("DELETE FROM booking WHERE booking_id = 1")
        conn.commit()
        cur.close()
        return "Unexpectedly deleted!"

    run_and_log(lines, "ALLOWED: SELECT utilization report v_resource_utilization", fm_allowed)
    run_and_log(lines, "DENIED : DELETE FROM booking", fm_denied)
    conn.close()

    # 3. SECURITY (sec_auditor)
    sec_user = os.getenv("MYSQL_SEC_USER", "sec_auditor")
    sec_pass = os.getenv("MYSQL_SEC_PASSWORD")
    lines.append(f"\n--- ROLE 3: security (user: {sec_user}) ---")
    conn = connect_as(sec_user, sec_pass)
    show_grants_for(lines, conn)

    def sec_allowed():
        cur = conn.cursor()
        cur.execute("SELECT log_id, booking_id, check_in_time FROM access_log LIMIT 3")
        rows = cur.fetchall()
        cur.close()
        return f"access_log sample: {len(rows)} row(s)"

    def sec_denied():
        cur = conn.cursor()
        cur.execute("SELECT emp_id, email, phone FROM employee LIMIT 1")
        rows = cur.fetchall()
        cur.close()
        return f"Unexpectedly read employee: {rows}"

    run_and_log(lines, "ALLOWED: SELECT from access_log", sec_allowed)
    run_and_log(lines, "DENIED : SELECT from employee (personal data)", sec_denied)
    conn.close()

    # 4. ADMIN (office_admin)
    adm_user = os.getenv("MYSQL_ADMIN_USER", "office_admin")
    adm_pass = os.getenv("MYSQL_ADMIN_PASSWORD")
    lines.append(f"\n--- ROLE 4: admin (user: {adm_user}) ---")
    conn = connect_as(adm_user, adm_pass)
    show_grants_for(lines, conn)

    def adm_allowed():
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM booking")
        cnt = cur.fetchone()[0]
        cur.close()
        return f"Full access verified: booking has {cnt} rows"

    def adm_denied_on_mysql_sys():
        cur = conn.cursor()
        cur.execute("SELECT user, host FROM mysql.user LIMIT 1")
        rows = cur.fetchall()
        cur.close()
        return f"Unexpectedly read mysql.user: {rows}"

    run_and_log(lines, "ALLOWED: SELECT COUNT(*) FROM smart_office.booking", adm_allowed)
    run_and_log(lines, "DENIED : SELECT FROM mysql.user (scoped to smart_office.* only)", adm_denied_on_mysql_sys)
    conn.close()

    # 5. REVOKE DEMO (revoke SELECT on v_resource_utilization from facility_manager, verify DENIED, then restore)
    lines.append("\n--- REVOKE DEMO (facility_manager loses v_resource_utilization) ---")
    root_conn = connect_as(os.getenv("MYSQL_USER", "root"), os.getenv("MYSQL_PASSWORD"))
    rcur = root_conn.cursor()
    rcur.execute("REVOKE SELECT ON smart_office.v_resource_utilization FROM 'facility_manager'")
    rcur.execute("FLUSH PRIVILEGES")
    lines.append("  Admin executed: REVOKE SELECT ON smart_office.v_resource_utilization FROM 'facility_manager'")

    fm_conn = connect_as(fm_user, fm_pass)
    def fm_after_revoke():
        cur = fm_conn.cursor()
        cur.execute("SELECT * FROM v_resource_utilization LIMIT 1")
        cur.fetchall()
        cur.close()
        return "Unexpectedly succeeded!"

    run_and_log(lines, "AFTER REVOKE: fm_user queries v_resource_utilization", fm_after_revoke)
    fm_conn.close()

    # Restore privilege so environment remains clean
    rcur.execute("GRANT SELECT ON smart_office.v_resource_utilization TO 'facility_manager'")
    rcur.execute("FLUSH PRIVILEGES")
    rcur.close()
    root_conn.close()
    lines.append("  Admin restored: GRANT SELECT ON smart_office.v_resource_utilization TO 'facility_manager'")

    output_text = "\n".join(lines) + "\n"
    OUT_FILE.write_text(output_text, encoding="utf-8")
    print(output_text)
    print(f"Saved output to: {OUT_FILE}")


if __name__ == "__main__":
    main()
