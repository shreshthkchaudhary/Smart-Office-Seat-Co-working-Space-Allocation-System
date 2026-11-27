"""
app/app.py
Task T4: Smart Office Seat & Co-working Space Allocation Flask App.
- Connects to MySQL as the low-privilege 'employee' role user (emp_5), NEVER root.
- Uses strictly parameterized queries (%s) and stored procedures (callproc).
- Displays the stored procedure's OUT p_message directly to the user.
- Default booking/search date is 2026-12-01 (weekday after sample dataset).
"""

import os
from pathlib import Path
from flask import Flask, flash, redirect, render_template, request, session, url_for
import mysql.connector
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "smart-office-capstone-dev-key")


def get_db():
    """Open a MySQL connection using environment variables (supports Railway & local)."""
    host = os.getenv("MYSQLHOST") or os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQLPORT") or os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_EMP_USER") or os.getenv("MYSQLUSER") or os.getenv("MYSQL_USER", "emp_5")
    password = os.getenv("MYSQL_EMP_PASSWORD") or os.getenv("MYSQLPASSWORD") or os.getenv("MYSQL_PASSWORD")
    database = os.getenv("MYSQLDATABASE") or os.getenv("MYSQL_DATABASE", "smart_office")

    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )


def get_employees():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT emp_id, name, role, dept_name FROM v_employee_directory ORDER BY emp_id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@app.context_processor
def inject_globals():
    if "emp_id" not in session:
        session["emp_id"] = 5
    employees = get_employees()
    current_emp = next((e for e in employees if e["emp_id"] == session["emp_id"]), None)
    return {
        "employees": employees,
        "current_emp_id": session["emp_id"],
        "current_emp": current_emp,
        "db_user": os.getenv("MYSQL_EMP_USER", "emp_5"),
    }


@app.route("/login_as", methods=["POST"])
def login_as():
    emp_id = request.form.get("emp_id", type=int)
    if emp_id:
        session["emp_id"] = emp_id
        flash(f"Switched active employee to emp_id={emp_id}.", "info")
    return redirect(request.referrer or url_for("index"))


@app.route("/", methods=["GET"])
def index():
    booking_date = request.args.get("date", "2026-12-01")
    start_time = request.args.get("start_time", "10:00")
    end_time = request.args.get("end_time", "12:00")
    res_type = request.args.get("resource_type", "All")
    min_cap = request.args.get("min_capacity", default=1, type=int)

    # Normalize HH:MM to HH:MM:SS for MySQL TIME comparison
    start_sql = f"{start_time}:00" if len(start_time) == 5 else start_time
    end_sql = f"{end_time}:00" if len(end_time) == 5 else end_time

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Parameterized availability query using fn_is_available() (BR4, BR5, BR6, BR7)
    sql = """
        SELECT r.resource_id, r.resource_code, r.resource_type, r.status,
               z.zone_name, f.floor_no, o.city,
               d.desk_type, rm.room_name, rm.capacity,
               fn_is_available(r.resource_id, %s, %s, %s) AS is_free
        FROM resource r
        JOIN zone z   ON z.zone_id   = r.zone_id
        JOIN floor f  ON f.floor_id  = z.floor_id
        JOIN office o ON o.office_id = f.office_id
        LEFT JOIN desk d  ON d.resource_id  = r.resource_id
        LEFT JOIN room rm ON rm.resource_id = r.resource_id
        WHERE r.status = 'Active'
    """
    params: list = [booking_date, start_sql, end_sql]

    if res_type in ("Desk", "Room"):
        sql += " AND r.resource_type = %s"
        params.append(res_type)

    if min_cap and min_cap > 1:
        sql += " AND (r.resource_type = 'Room' AND rm.capacity >= %s)"
        params.append(min_cap)

    sql += " ORDER BY is_free DESC, r.resource_type, r.resource_code"
    cur.execute(sql, tuple(params))
    resources = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        "index.html",
        resources=resources,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        res_type=res_type,
        min_cap=min_cap,
    )


@app.route("/book", methods=["POST"])
def book():
    emp_id = session.get("emp_id", 5)
    resource_id = request.form.get("resource_id", type=int)
    booking_date = request.form.get("booking_date", "2026-12-01")
    start_time = request.form.get("start_time", "10:00")
    end_time = request.form.get("end_time", "12:00")
    attendees = request.form.get("attendees", default=1, type=int)

    start_sql = f"{start_time}:00" if len(start_time) == 5 else start_time
    end_sql = f"{end_time}:00" if len(end_time) == 5 else end_time

    conn = get_db()
    cur = conn.cursor()
    result = cur.callproc(
        "sp_book_resource",
        (emp_id, resource_id, booking_date, start_sql, end_sql, attendees, 0, ""),
    )
    booking_id, msg = result[6], result[7]
    cur.close()
    conn.close()

    category = "success" if str(msg).startswith("SUCCESS") else "error"
    flash(f"{msg}" + (f" (Booking ID: {booking_id})" if booking_id else ""), category)
    return redirect(
        url_for("index", date=booking_date, start_time=start_time, end_time=end_time)
    )


@app.route("/my-bookings", methods=["GET"])
def my_bookings():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    # BR14: v_my_bookings automatically filters by connected MySQL USER() (emp_5 -> emp_id=5)
    cur.execute("""
        SELECT booking_id, emp_id, employee_name, resource_code, resource_type,
               zone_name, floor_no, city, booking_date, start_time, end_time, attendees, status
        FROM v_my_bookings
        ORDER BY booking_date DESC, start_time DESC
    """)
    bookings = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("my_bookings.html", bookings=bookings)


@app.route("/cancel/<int:booking_id>", methods=["POST"])
def cancel(booking_id: int):
    emp_id = session.get("emp_id", 5)
    reason = request.form.get("reason", "Cancelled via web app")

    conn = get_db()
    cur = conn.cursor()
    result = cur.callproc("sp_cancel_booking", (booking_id, emp_id, reason, ""))
    msg = result[3]
    cur.close()
    conn.close()

    category = "success" if str(msg).startswith("SUCCESS") else "error"
    flash(msg, category)
    return redirect(url_for("my_bookings"))


@app.route("/checkin/<int:booking_id>", methods=["POST"])
def checkin(booking_id: int):
    check_time = request.form.get("check_time", "").strip()
    p_time = check_time if check_time else None

    conn = get_db()
    cur = conn.cursor()
    result = cur.callproc("sp_check_in", (booking_id, p_time, ""))
    msg = result[2]
    cur.close()
    conn.close()

    category = "success" if str(msg).startswith("SUCCESS") else "error"
    flash(msg, category)
    return redirect(url_for("my_bookings"))


@app.route("/utilization", methods=["GET"])
def utilization():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT resource_id, resource_code, resource_type, booked_hours, util_pct
        FROM v_resource_utilization
        ORDER BY util_pct DESC, resource_code
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("utilization.html", rows=rows)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
