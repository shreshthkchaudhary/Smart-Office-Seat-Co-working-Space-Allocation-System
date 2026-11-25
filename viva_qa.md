# Viva Preparation — 25 Likely Examiner Questions & Simple Answers
**Course:** ETCCMS304 (DBMS) | **Project 3:** Smart Office Seat & Co-working Space Allocation System

---

### A. ER Modeling & Normalization
1. **Why did you use specialization (`RESOURCE` → `DESK` and `ROOM`) instead of one big table?**
   - Both desks and rooms share `resource_code`, `status`, and `zone_id`, and both are booked in `BOOKING`. Keeping common columns in `RESOURCE` avoids duplicate FKs, while `DESK` (`desk_type`) and `ROOM` (`capacity`) hold subtype-only attributes without `NULL`s.
2. **What is the difference between 3NF and BCNF, and is your schema in BCNF?**
   - In 3NF, no non-key attribute is transitively dependent on a candidate key. BCNF is stricter: for every non-trivial FD `X → Y`, `X` must be a superkey. All 13 of our tables are in **BCNF** because every determinant is a primary or unique candidate key.
3. **Why isn't "no overlapping bookings" enforced by a functional dependency or `UNIQUE` constraint?**
   - `UNIQUE (resource_id, booking_date, start_time, end_time)` only blocks *identical* start/end times—it would still allow `10:00–12:00` and `11:00–13:00` to overlap! That is why we enforce BR5 in `sp_book_resource` using `start_time < p_end AND end_time > p_start` with row locking.
4. **Why did you not store `dept_name` or `duration_hours` in the `BOOKING` table?**
   - Storing `dept_name` in `BOOKING` would create a transitive dependency (`booking_id → emp_id → dept_id → dept_name`), violating 3NF. Duration is derived from `end_time - start_time`, so storing it would risk inconsistency.

### B. SQL, Views & Indexes
5. **What is the difference between `WHERE` and `HAVING`?**
   - `WHERE` filters individual rows *before* grouping; `HAVING` filters grouped results *after* `GROUP BY` (for example, `HAVING COUNT(*) > avg` in Q7).
6. **How did you use Window Functions and CTEs?**
   - We used `RANK()` / `DENSE_RANK()` to rank zones by utilization, `SUM() OVER` and `LAG()` for daily running totals, and CTEs (`WITH`) to calculate monthly/weekly occupancy and find below-average resources (Q19).
7. **How did your two indexes (`idx_booking_overlap`, `idx_booking_date_status`) improve performance?**
   - `EXPLAIN` showed the overlap query switched from scanning all bookings for a resource (`ref`) to an index range scan on `(resource_id, booking_date, start_time, end_time)`, and the daily report switched from a full table scan (`ALL`) to `index`/`range`.
8. **What is a View, and why is `v_current_availability` a view instead of a table?**
   - A view is a saved virtual query. Availability changes every minute (`CURDATE()` / `CURTIME()`), so a view always computes live availability without storing stale data.

### C. Triggers, Functions & Stored Procedures
9. **When do you use a Trigger vs. a Stored Procedure?**
   - A **trigger** runs automatically on `INSERT`/`UPDATE` regardless of who modifies the table (e.g., `trg_booking_bi` always checks BR6/BR7/BR12, and `trg_booking_au_audit` always logs status changes). A **stored procedure** is called explicitly for multi-step workflows that need transactions and `OUT` messages (e.g., `sp_book_resource`).
10. **Why couldn't `trg_booking_bi` handle the overlap check (BR5) by itself?**
    - Under concurrency, two sessions inserting at the same time would both pass a trigger check before either commits. Putting `SELECT ... FOR UPDATE` inside `sp_book_resource` locks the parent `resource` row first so sessions run one after another.
11. **What is the difference between a Stored Function and a Stored Procedure in MySQL?**
    - A **function** (`fn_is_available`, `fn_utilization_pct`) returns a single scalar value and can be used inside `SELECT` queries, and cannot manage transactions. A **procedure** (`sp_book_resource`) can use `START TRANSACTION`/`COMMIT`/`ROLLBACK` and return multiple `OUT` parameters.

### D. Transactions, Concurrency & Locking
12. **What are ACID properties, and where does your project show each one?**
    - **Atomicity**: `sp_cancel_booking` inserts into `cancellation` and updates `booking` together (or rolls back both). **Consistency**: CHECK constraints and triggers block invalid capacity/dates. **Isolation**: `FOR UPDATE` prevents double-booking. **Durability**: InnoDB commits persist to disk.
13. **What is `SAVEPOINT` used for?**
    - `SAVEPOINT` creates a partial rollback marker inside a transaction so you can undo a failed sub-step (`ROLLBACK TO SAVEPOINT sp1`) without losing earlier valid work in the same transaction (verified in `TC21`).
14. **What is MySQL's default isolation level, and how does it affect double-booking?**
    - MySQL InnoDB's default is **`REPEATABLE READ`**. Without locking, two concurrent transactions see the same snapshot (0 conflicts) and both insert overlapping bookings. Using `SELECT ... FOR UPDATE` performs a locking read on the latest committed data and blocks the second session until the first commits.
15. **What is a deadlock, and how do you prevent it?**
    - A deadlock happens when Session 1 locks Resource A and waits for Resource B, while Session 2 locks Resource B and waits for Resource A (MySQL Error `1213`). We prevent it by always locking resources in a consistent order (e.g., ascending `resource_id`).

### E. Security (RBAC & SQL Injection)
16. **How does your RBAC follow the Principle of Least Privilege?**
    - Employees (`emp_5`) have **zero** direct `SELECT`/`INSERT`/`UPDATE`/`DELETE` on `booking`—they can only execute `sp_book_resource`, `sp_cancel_booking`, `sp_check_in`, and read safe views. `security` (`sec_auditor`) can only read `access_log` and `v_booking_details`.
17. **How does `v_my_bookings` enforce BR14 (employees see only their own bookings)?**
    - It uses `USER()` (which returns `'emp_5@localhost'`), extracts `5` from the username, and filters `WHERE b.emp_id = 5`. Even though the view runs with `DEFINER` privileges, `USER()` always identifies the connected client.
18. **How does `emp_5` book a row if they don't have `INSERT` privilege on `booking`?**
    - Stored procedures in MySQL default to `SQL SECURITY DEFINER`, meaning `sp_book_resource` runs with the definer's (`root`) privileges after validating all business rules.
19. **What is SQL Injection, and how did you prevent it?**
    - SQL Injection happens when user input is concatenated into a SQL string (e.g., `' OR '1'='1` leaked all 47 available resources, and `UNION SELECT` leaked 40 employee records). We prevent it using **parameterized queries (`%s`)** and **stored procedures (`callproc`)**, which treat input strictly as data.

### F. NoSQL (MongoDB) & Application Integration
20. **Why use both MySQL and MongoDB instead of only one database?**
    - MySQL excels at structured, relational bookings needing ACID transactions and `FOR UPDATE` locking. MongoDB excels at semi-structured workspace metadata (varying desk/room equipment, accessibility flags, IoT sensors) without `NULL` columns or schema migrations.
21. **What is a multikey index in MongoDB?**
    - An index on an array field (like `amenities`). MongoDB indexes every element of the array so queries like "find rooms with Projector" are fast.
22. **Explain one MongoDB aggregation pipeline you implemented.**
    - Pipeline 1 uses `$unwind: "$amenities"` to flatten each resource's amenity array, `$group` to count resources per amenity, and `$sort` descending (`Power Outlets: 50`, `Docking Station: 20`, `Monitor: 20`).

### G. Testing & Operations
23. **How did you test concurrency in Python?**
    - In `09_tests/run_tests.py` (`TC22`), two `threading.Thread` workers open separate MySQL connections, synchronize at a `threading.Barrier(2)`, and call `sp_book_resource` simultaneously for overlapping slots (`10:00–12:00` and `11:00–13:00`) on the same desk. Result: **1 SUCCESS, 1 REJECTED**.
24. **How are No-Shows handled in your system (BR11)?**
    - `sp_mark_no_shows(p_now, @updated)` finds `Confirmed` bookings with no `access_log` entry more than 15 minutes after `start_time` and marks them `No-Show` (which Trigger 2 logs in `booking_audit`).
25. **Why did you use `.env` and `.gitignore`?**
    - Never hard-coding database passwords in source code prevents credential leaks in Git/GitHub. `.env.example` documents the required variables safely.
