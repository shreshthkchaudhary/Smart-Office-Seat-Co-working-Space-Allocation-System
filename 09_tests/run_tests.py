"""
09_tests/run_tests.py
Task T5: Comprehensive Automated Test Suite (22 Test Cases)
Covers: Positive, Negative (BR5-BR14), Integrity (PK/FK/UNIQUE/CHECK),
        Transactions (COMMIT/ROLLBACK/SAVEPOINT), and Concurrency (2 real threads).
Uses dates >= 2026-12-01 and cleans up all added rows so the DB stays unchanged.
Outputs:
  - 09_tests/test_results.csv
  - 09_tests/test_results.md
"""

import csv
import os
import threading
from pathlib import Path
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

OUT_DIR = Path(__file__).resolve().parent
CSV_PATH = OUT_DIR / "test_results.csv"
MD_PATH = OUT_DIR / "test_results.md"


def get_conn(user_env="MYSQL_USER", pass_env="MYSQL_PASSWORD"):
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv(user_env, "root"),
        password=os.getenv(pass_env),
        database=os.getenv("MYSQL_DATABASE", "smart_office"),
    )


def main():
    root = get_conn()
    cur = root.cursor(dictionary=True)

    # Record initial booking count for cleanup verification
    cur.execute("SELECT COUNT(*) AS cnt FROM booking")
    initial_booking_count = cur.fetchone()["cnt"]

    # Dynamically look up real IDs from smart_office
    cur.execute("SELECT resource_id FROM resource WHERE resource_type='Desk' AND status='Active' ORDER BY resource_id LIMIT 1")
    active_desk_id = cur.fetchone()["resource_id"]

    cur.execute("""
        SELECT r.resource_id, rm.capacity
        FROM resource r JOIN room rm ON rm.resource_id = r.resource_id
        WHERE r.status='Active' ORDER BY r.resource_id LIMIT 1
    """)
    room_row = cur.fetchone()
    active_room_id = room_row["resource_id"]
    active_room_cap = room_row["capacity"]

    cur.execute("SELECT resource_id FROM resource WHERE status <> 'Active' ORDER BY resource_id LIMIT 1")
    inactive_row = cur.fetchone()
    inactive_res_id = inactive_row["resource_id"] if inactive_row else None

    cur.execute("SELECT email FROM employee LIMIT 1")
    existing_email = cur.fetchone()["email"]

    created_booking_ids: list[int] = []
    results: list[dict] = []

    def record(tc_id: str, tc_type: str, desc: str, inp: str, expected: str, actual: str, passed: bool):
        results.append({
            "ID": tc_id,
            "Type": tc_type,
            "Description": desc,
            "Input": inp,
            "Expected": expected,
            "Actual": actual,
            "Status": "PASS" if passed else "FAIL",
        })

    try:
        # ------------------------------------------------------------------
        # 1. POSITIVE TESTS
        # ------------------------------------------------------------------
        c = root.cursor()
        res = c.callproc("sp_book_resource", (5, active_desk_id, "2026-12-01", "10:00:00", "12:00:00", 1, 0, ""))
        b1_id, b1_msg = res[6], res[7]
        if b1_id:
            created_booking_ids.append(b1_id)
        record("TC01", "Positive", "Book active desk via sp_book_resource",
               f"emp=5, desk={active_desk_id}, 2026-12-01 10:00-12:00",
               "SUCCESS: booking confirmed", b1_msg, b1_msg == "SUCCESS: booking confirmed")

        # TC02: Adjacent non-overlapping slot (BR5 boundary)
        res = c.callproc("sp_book_resource", (6, active_desk_id, "2026-12-01", "12:00:00", "14:00:00", 1, 0, ""))
        b2_id, b2_msg = res[6], res[7]
        if b2_id:
            created_booking_ids.append(b2_id)
        record("TC02", "Positive", "Book adjacent slot 12:00-14:00 (BR5 boundary)",
               f"emp=6, desk={active_desk_id}, 2026-12-01 12:00-14:00",
               "SUCCESS: booking confirmed", b2_msg, b2_msg == "SUCCESS: booking confirmed")

        # TC03: Book active room within capacity (BR6)
        res = c.callproc("sp_book_resource", (5, active_room_id, "2026-12-02", "10:00:00", "12:00:00", active_room_cap, 0, ""))
        b3_id, b3_msg = res[6], res[7]
        if b3_id:
            created_booking_ids.append(b3_id)
        record("TC03", "Positive", "Book active room at exact capacity (BR6)",
               f"emp=5, room={active_room_id}, attendees={active_room_cap}",
               "SUCCESS: booking confirmed", b3_msg, b3_msg == "SUCCESS: booking confirmed")

        # TC04: Check-in within 15-min window (BR10)
        res = c.callproc("sp_check_in", (b1_id, "2026-12-01 09:55:00", ""))
        ci_msg = res[2]
        record("TC04", "Positive", "Check in 5 mins before start (BR10)",
               f"booking_id={b1_id}, time=2026-12-01 09:55:00",
               "SUCCESS: checked in", ci_msg, ci_msg == "SUCCESS: checked in")

        # TC05: Cancel own Confirmed booking before start (BR9, BR14) + audit trigger
        res = c.callproc("sp_cancel_booking", (b2_id, 6, "Meeting moved", ""))
        can_msg = res[3]
        c.execute("SELECT COUNT(*) FROM booking_audit WHERE booking_id=%s AND new_status='Cancelled'", (b2_id,))
        audit_cnt = c.fetchone()[0]
        record("TC05", "Positive", "Owner cancels booking + audit trigger (BR9)",
               f"booking_id={b2_id}, emp=6",
               "SUCCESS: booking cancelled + audit=1", f"{can_msg} (audit={audit_cnt})",
               can_msg == "SUCCESS: booking cancelled" and audit_cnt == 1)

        # ------------------------------------------------------------------
        # 2. NEGATIVE TESTS (BUSINESS RULE VIOLATIONS)
        # ------------------------------------------------------------------
        # TC06: Overlapping slot (BR5)
        res = c.callproc("sp_book_resource", (7, active_desk_id, "2026-12-01", "11:00:00", "13:00:00", 1, 0, ""))
        if res[6]:
            created_booking_ids.append(res[6])
        record("TC06", "Negative (BR5)", "Reject overlapping booking on same desk",
               f"emp=7, desk={active_desk_id}, 2026-12-01 11:00-13:00",
               "REJECTED: time slot overlaps", res[7], "overlaps" in res[7])

        # TC07: Exceed room capacity (BR6)
        res = c.callproc("sp_book_resource", (5, active_room_id, "2026-12-02", "14:00:00", "15:00:00", active_room_cap + 5, 0, ""))
        if res[6]:
            created_booking_ids.append(res[6])
        record("TC07", "Negative (BR6)", "Reject room booking exceeding capacity",
               f"room={active_room_id}, attendees={active_room_cap + 5} > {active_room_cap}",
               "REJECTED: BR6 attendees exceed capacity", res[7], "BR6" in res[7])

        # TC08: Book Maintenance/Inactive resource (BR7)
        if inactive_res_id is not None:
            res = c.callproc("sp_book_resource", (5, inactive_res_id, "2026-12-02", "10:00:00", "11:00:00", 1, 0, ""))
            if res[6]:
                created_booking_ids.append(res[6])
            record("TC08", "Negative (BR7)", "Reject booking on Maintenance/Inactive resource",
                   f"resource_id={inactive_res_id}",
                   "REJECTED: BR7 maintenance/inactive", res[7], "BR7" in res[7])
        else:
            record("TC08", "Negative (BR7)", "Reject booking on Maintenance/Inactive resource",
                   "N/A", "REJECTED: BR7", "No inactive resource in DB", False)

        # TC09: Room duration > 4 hours (BR12)
        res = c.callproc("sp_book_resource", (5, active_room_id, "2026-12-02", "13:00:00", "18:00:00", 2, 0, ""))
        if res[6]:
            created_booking_ids.append(res[6])
        record("TC09", "Negative (BR12)", "Reject room booking > 4 hours",
               f"room={active_room_id}, 13:00-18:00 (5h)",
               "REJECTED: BR12 max 4 hours", res[7], "BR12" in res[7])

        # TC10: Desk duration > 9 hours (BR12)
        res = c.callproc("sp_book_resource", (5, active_desk_id, "2026-12-02", "08:00:00", "18:00:00", 1, 0, ""))
        if res[6]:
            created_booking_ids.append(res[6])
        record("TC10", "Negative (BR12)", "Reject desk booking > 9 hours",
               f"desk={active_desk_id}, 08:00-18:00 (10h)",
               "REJECTED: BR12 max 9 hours", res[7], "BR12" in res[7])

        # TC11: Check-in outside 15-min window (BR10)
        res = c.callproc("sp_check_in", (b3_id, "2026-12-02 09:00:00", ""))
        record("TC11", "Negative (BR10)", "Reject check-in 60 mins before start",
               f"booking_id={b3_id}, time=09:00 (start=10:00)",
               "REJECTED: check-in 15 min window", res[2], "15 minutes" in res[2])

        # TC12: Non-owner tries to cancel (BR14)
        res = c.callproc("sp_cancel_booking", (b3_id, 6, "Unauthorized cancel", ""))
        record("TC12", "Negative (BR14)", "Reject cancel by non-owner employee",
               f"booking_id={b3_id} (owner=5), caller=6",
               "REJECTED: only cancel your own bookings", res[3], "own bookings" in res[3])

        # TC13: Re-cancel already-cancelled booking (BR9)
        res = c.callproc("sp_cancel_booking", (b2_id, 6, "Cancel twice", ""))
        record("TC13", "Negative (BR9)", "Reject cancelling an already-cancelled booking",
               f"booking_id={b2_id} (already Cancelled)",
               "REJECTED: BR9 only Confirmed", res[3], "BR9" in res[3])

        # ------------------------------------------------------------------
        # 3. INTEGRITY CONSTRAINTS (PK / FK / UNIQUE / CHECK)
        # ------------------------------------------------------------------
        # TC14: PK violation
        try:
            c.execute("INSERT INTO department (dept_id, dept_name) VALUES (1, 'DupPKDept')")
            root.commit()
            record("TC14", "Integrity (PK)", "Reject duplicate Primary Key on department",
                   "dept_id=1", "MySQL Error 1062 Duplicate", "Inserted unexpectedly", False)
        except Error as e:
            root.rollback()
            record("TC14", "Integrity (PK)", "Reject duplicate Primary Key on department",
                   "dept_id=1", "MySQL Error 1062 Duplicate", f"Error {e.errno}: {e.msg}", e.errno == 1062)

        # TC15: FK violation
        try:
            c.execute(
                "INSERT INTO booking (emp_id, resource_id, booking_date, start_time, end_time, attendees) "
                "VALUES (999999, %s, '2026-12-04', '10:00:00', '11:00:00', 1)", (active_desk_id,)
            )
            root.commit()
            record("TC15", "Integrity (FK)", "Reject nonexistent emp_id Foreign Key",
                   "emp_id=999999", "MySQL Error 1452 FK", "Inserted unexpectedly", False)
        except Error as e:
            root.rollback()
            record("TC15", "Integrity (FK)", "Reject nonexistent emp_id Foreign Key",
                   "emp_id=999999", "MySQL Error 1452 FK", f"Error {e.errno}: {e.msg[:65]}", e.errno == 1452)

        # TC16: UNIQUE violation
        try:
            c.execute("INSERT INTO employee (name, email, role, dept_id) VALUES ('Test', %s, 'Employee', 1)", (existing_email,))
            root.commit()
            record("TC16", "Integrity (UNIQUE)", "Reject duplicate employee email",
                   f"email={existing_email}", "MySQL Error 1062 Duplicate", "Inserted unexpectedly", False)
        except Error as e:
            root.rollback()
            record("TC16", "Integrity (UNIQUE)", "Reject duplicate employee email",
                   f"email={existing_email}", "MySQL Error 1062 Duplicate", f"Error {e.errno}: {e.msg}", e.errno == 1062)

        # TC17: CHECK chk_book_time
        try:
            c.execute(
                "INSERT INTO booking (emp_id, resource_id, booking_date, start_time, end_time, attendees) "
                "VALUES (5, %s, '2026-12-04', '14:00:00', '12:00:00', 1)", (active_desk_id,)
            )
            root.commit()
            record("TC17", "Integrity (CHECK)", "Reject end_time <= start_time (chk_book_time)",
                   "14:00:00 to 12:00:00", "MySQL Error 3819 CHECK", "Inserted unexpectedly", False)
        except Error as e:
            root.rollback()
            record("TC17", "Integrity (CHECK)", "Reject end_time <= start_time (chk_book_time)",
                   "14:00:00 to 12:00:00", "MySQL Error 3819 CHECK", f"Error {e.errno}: {e.msg}", e.errno == 3819)

        # TC18: CHECK chk_emp_role
        try:
            c.execute("INSERT INTO employee (name, email, role, dept_id) VALUES ('BadRole', 'badrole@test.local', 'Intern', 1)")
            root.commit()
            record("TC18", "Integrity (CHECK)", "Reject invalid employee role (chk_emp_role)",
                   "role='Intern'", "MySQL Error 3819 CHECK", "Inserted unexpectedly", False)
        except Error as e:
            root.rollback()
            record("TC18", "Integrity (CHECK)", "Reject invalid employee role (chk_emp_role)",
                   "role='Intern'", "MySQL Error 3819 CHECK", f"Error {e.errno}: {e.msg}", e.errno == 3819)

        # ------------------------------------------------------------------
        # 4. TRANSACTIONS (COMMIT / ROLLBACK / SAVEPOINT)
        # ------------------------------------------------------------------
        # TC19: COMMIT
        root.rollback()
        root.start_transaction()
        c.execute("INSERT INTO department (dept_name) VALUES ('__TestCommitDept__')")
        root.commit()
        c.execute("SELECT COUNT(*) FROM department WHERE dept_name='__TestCommitDept__'")
        cnt_commit = c.fetchone()[0]
        c.execute("DELETE FROM department WHERE dept_name='__TestCommitDept__'")
        root.commit()
        record("TC19", "Transaction (COMMIT)", "Committed row persists after COMMIT",
               "INSERT __TestCommitDept__ + COMMIT", "count=1", f"count={cnt_commit}", cnt_commit == 1)

        # TC20: ROLLBACK
        root.rollback()
        root.start_transaction()
        c.execute("INSERT INTO department (dept_name) VALUES ('__TestRollbackDept__')")
        root.rollback()
        c.execute("SELECT COUNT(*) FROM department WHERE dept_name='__TestRollbackDept__'")
        cnt_rb = c.fetchone()[0]
        record("TC20", "Transaction (ROLLBACK)", "Rolled-back row is undone",
               "INSERT __TestRollbackDept__ + ROLLBACK", "count=0", f"count={cnt_rb}", cnt_rb == 0)

        # TC21: SAVEPOINT
        root.rollback()
        root.start_transaction()
        c.execute("INSERT INTO department (dept_name) VALUES ('__TestSpA__')")
        c.execute("SAVEPOINT sp1")
        c.execute("INSERT INTO department (dept_name) VALUES ('__TestSpB__')")
        c.execute("ROLLBACK TO SAVEPOINT sp1")
        root.commit()
        c.execute("SELECT dept_name FROM department WHERE dept_name IN ('__TestSpA__', '__TestSpB__')")
        kept = [r[0] for r in c.fetchall()]
        c.execute("DELETE FROM department WHERE dept_name IN ('__TestSpA__', '__TestSpB__')")
        root.commit()
        record("TC21", "Transaction (SAVEPOINT)", "ROLLBACK TO sp1 keeps A and discards B",
               "Insert A, SAVEPOINT sp1, Insert B, ROLLBACK TO sp1, COMMIT",
               "['__TestSpA__']", str(kept), kept == ["__TestSpA__"])

        c.close()

        # ------------------------------------------------------------------
        # 5. CONCURRENCY TEST (2 real simultaneous connections)
        # ------------------------------------------------------------------
        barrier = threading.Barrier(2)
        conc_results = []
        conc_lock = threading.Lock()

        def worker(emp_id: int, start_t: str, end_t: str):
            w_conn = get_conn("MYSQL_EMP_USER", "MYSQL_EMP_PASSWORD")
            w_cur = w_conn.cursor()
            barrier.wait()  # Both threads hit sp_book_resource at the exact same instant
            res = w_cur.callproc(
                "sp_book_resource",
                (emp_id, active_desk_id, "2026-12-03", start_t, end_t, 1, 0, ""),
            )
            w_cur.close()
            w_conn.close()
            with conc_lock:
                conc_results.append((emp_id, res[6], res[7]))
                if res[6]:
                    created_booking_ids.append(res[6])

        t1 = threading.Thread(target=worker, args=(5, "10:00:00", "12:00:00"))
        t2 = threading.Thread(target=worker, args=(6, "11:00:00", "13:00:00"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        success_cnt = sum(1 for _, _, m in conc_results if str(m).startswith("SUCCESS"))
        rejected_cnt = sum(1 for _, _, m in conc_results if str(m).startswith("REJECTED"))
        conc_actual = "; ".join(f"emp={e}: {m}" for e, _, m in conc_results)
        record("TC22", "Concurrency", "2 simultaneous overlapping bookings on same desk",
               f"Thread1(10-12) & Thread2(11-13) on desk={active_desk_id}, 2026-12-03",
               "1 SUCCESS, 1 REJECTED", f"{success_cnt} SUCCESS, {rejected_cnt} REJECTED ({conc_actual})",
               success_cnt == 1 and rejected_cnt == 1)

    finally:
        # Clean up all test bookings so DB state is identical to before
        if created_booking_ids:
            clean_cur = root.cursor()
            fmt = ",".join(["%s"] * len(created_booking_ids))
            clean_cur.execute(f"DELETE FROM booking_audit WHERE booking_id IN ({fmt})", tuple(created_booking_ids))
            clean_cur.execute(f"DELETE FROM cancellation WHERE booking_id IN ({fmt})", tuple(created_booking_ids))
            clean_cur.execute(f"DELETE FROM access_log WHERE booking_id IN ({fmt})", tuple(created_booking_ids))
            clean_cur.execute(f"DELETE FROM booking WHERE booking_id IN ({fmt})", tuple(created_booking_ids))
            root.commit()
            clean_cur.close()

        cur.execute("SELECT COUNT(*) AS cnt FROM booking")
        final_booking_count = cur.fetchone()["cnt"]
        cur.close()
        root.close()

    # Write CSV
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ID", "Type", "Description", "Input", "Expected", "Actual", "Status"])
        writer.writeheader()
        writer.writerows(results)

    # Write Markdown table
    md_lines = [
        "| ID | Type | Description | Input | Expected | Actual | PASS/FAIL |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        md_lines.append(
            f"| {r['ID']} | {r['Type']} | {r['Description']} | `{r['Input']}` | {r['Expected']} | {r['Actual']} | **{r['Status']}** |"
        )
    MD_PATH.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    passed_total = sum(1 for r in results if r["Status"] == "PASS")
    print(f"\nTest Suite Complete: {passed_total}/{len(results)} PASSED")
    print(f"Booking rows before={initial_booking_count}, after cleanup={final_booking_count}")
    print(f"Saved: {CSV_PATH}")
    print(f"Saved: {MD_PATH}\n")
    for r in results:
        print(f"[{r['Status']}] {r['ID']} ({r['Type']}): {r['Description']} -> {r['Actual']}")


if __name__ == "__main__":
    main()
