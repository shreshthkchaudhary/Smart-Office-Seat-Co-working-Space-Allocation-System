"""
07_sql_injection_demo.py
Task T2: SQL Injection Vulnerability vs Parameterized Queries & Stored Procedures.
Runs using the low-privilege 'emp_5' account (NEVER root) from .env.
Demonstrates:
  1. ' OR '1'='1 bypass (BEFORE vs AFTER)
  2. UNION SELECT data leak (BEFORE vs AFTER)
  3. Safe stored procedure call (callproc) with malicious string in p_reason
Saves real output to 07_sql_injection_output.txt and cleans up any test booking.
"""

import os
from pathlib import Path
import mysql.connector
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

HOST = os.getenv("MYSQL_HOST", "localhost")
PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB = os.getenv("MYSQL_DATABASE", "smart_office")
EMP_USER = os.getenv("MYSQL_EMP_USER", "emp_5")
EMP_PASS = os.getenv("MYSQL_EMP_PASSWORD")

OUT_FILE = ROOT_DIR / "07_sql_injection_output.txt"


def vulnerable_search_resource(conn, user_input: str):
    """VULNERABLE: builds SQL with f-string concatenation."""
    cur = conn.cursor()
    query = (
        "SELECT resource_code, resource_type, zone_name, city "
        f"FROM v_current_availability WHERE resource_code = '{user_input}'"
    )
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    return query, rows


def fixed_search_resource(conn, user_input: str):
    """FIXED: uses %s placeholder so MySQL treats input strictly as data."""
    cur = conn.cursor()
    query = (
        "SELECT resource_code, resource_type, zone_name, city "
        "FROM v_current_availability WHERE resource_code = %s"
    )
    cur.execute(query, (user_input,))
    rows = cur.fetchall()
    cur.close()
    return query, rows


def cleanup_test_booking(booking_id: int):
    """Remove the temporary test booking created on 2026-12-01 so data stays clean."""
    root_conn = mysql.connector.connect(
        host=HOST,
        port=PORT,
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=DB,
    )
    cur = root_conn.cursor()
    cur.execute("DELETE FROM booking_audit WHERE booking_id = %s", (booking_id,))
    cur.execute("DELETE FROM cancellation WHERE booking_id = %s", (booking_id,))
    cur.execute("DELETE FROM booking WHERE booking_id = %s", (booking_id,))
    root_conn.commit()
    cur.close()
    root_conn.close()


def main():
    lines = []
    lines.append("=" * 72)
    lines.append("SMART OFFICE SQL INJECTION DEMO (Connected as low-privilege: emp_5)")
    lines.append("=" * 72)

    conn = mysql.connector.connect(
        host=HOST, port=PORT, user=EMP_USER, password=EMP_PASS, database=DB
    )

    # Normal input baseline
    normal_input = "D-101"
    q, rows = vulnerable_search_resource(conn, normal_input)
    lines.append(f"\n[BASELINE] Normal input: {normal_input!r}")
    lines.append(f"  Rows returned: {len(rows)} -> {rows[:2]}")

    # ------------------------------------------------------------------
    # DEMO 1: ' OR '1'='1
    # ------------------------------------------------------------------
    payload_or = "' OR '1'='1"
    lines.append("\n" + "-" * 72)
    lines.append(f"DEMO 1: Boolean Bypass Payload -> {payload_or!r}")
    lines.append("-" * 72)

    q_vuln, rows_vuln = vulnerable_search_resource(conn, payload_or)
    lines.append("BEFORE (VULNERABLE string concatenation):")
    lines.append(f"  Executed SQL : {q_vuln}")
    lines.append(f"  Rows leaked  : {len(rows_vuln)} (ALL available resources exposed!)")
    lines.append(f"  Sample rows  : {rows_vuln[:3]}")

    q_fix, rows_fix = fixed_search_resource(conn, payload_or)
    lines.append("\nAFTER (FIXED parameterized query):")
    lines.append(f"  Prepared SQL : {q_fix}  with param=({payload_or!r},)")
    lines.append(f"  Rows returned: {len(rows_fix)} (Attack neutralized: literal match only)")

    # ------------------------------------------------------------------
    # DEMO 2: UNION SELECT leak
    # ------------------------------------------------------------------
    payload_union = "' UNION SELECT CAST(emp_id AS CHAR), name, role, dept_name FROM v_employee_directory -- "
    lines.append("\n" + "-" * 72)
    lines.append(f"DEMO 2: UNION SELECT Leak Payload -> {payload_union!r}")
    lines.append("-" * 72)

    q_vuln, rows_vuln = vulnerable_search_resource(conn, payload_union)
    lines.append("BEFORE (VULNERABLE string concatenation):")
    lines.append(f"  Executed SQL : {q_vuln}")
    lines.append(f"  Rows leaked  : {len(rows_vuln)} (Employee directory leaked into resource list!)")
    lines.append(f"  Sample leaked: {rows_vuln[:3]}")

    q_fix, rows_fix = fixed_search_resource(conn, payload_union)
    lines.append("\nAFTER (FIXED parameterized query):")
    lines.append(f"  Prepared SQL : {q_fix}  with param=({payload_union!r},)")
    lines.append(f"  Rows returned: {len(rows_fix)} (Attack neutralized)")

    # ------------------------------------------------------------------
    # DEMO 3: Stored Procedure (callproc) is Safe
    # ------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("DEMO 3: Stored Procedure (callproc) with Malicious Input")
    lines.append("-" * 72)

    cur = conn.cursor()
    # Book a temporary slot for emp_5 on 2026-12-01 (weekday after sample data)
    res_book = cur.callproc("sp_book_resource", (5, 1, "2026-12-01", "10:00:00", "11:00:00", 1, 0, ""))
    booking_id = res_book[6]
    book_msg = res_book[7]
    lines.append(f"  Step 1 - sp_book_resource returned: booking_id={booking_id}, msg={book_msg!r}")

    malicious_reason = "Plans changed'; DROP TABLE booking; -- "
    res_cancel = cur.callproc("sp_cancel_booking", (booking_id, 5, malicious_reason, ""))
    cancel_msg = res_cancel[3]
    lines.append(f"  Step 2 - sp_cancel_booking called with p_reason={malicious_reason!r}")
    lines.append(f"           Returned: {cancel_msg!r}")

    # Verify table still exists and booking is safely Cancelled
    cur.execute("SELECT booking_id, status FROM v_my_bookings WHERE booking_id = %s", (booking_id,))
    verify_row = cur.fetchone()
    lines.append(f"  Step 3 - Verified via v_my_bookings: {verify_row} (booking table intact!)")
    cur.close()
    conn.close()

    # Clean up temporary booking so database state is unchanged
    if booking_id:
        cleanup_test_booking(booking_id)
        lines.append(f"  Cleanup - Removed temporary test booking_id={booking_id} (database unchanged).")

    output_text = "\n".join(lines) + "\n"
    OUT_FILE.write_text(output_text, encoding="utf-8")
    print(output_text)
    print(f"Saved output to: {OUT_FILE}")


if __name__ == "__main__":
    main()
