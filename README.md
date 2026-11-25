# Smart Office Seat & Co-working Space Allocation System
**Course:** ETCCMS304 — Database Management Systems (B.Tech. CSE, Semester III)  
**Project:** Project 3 (DBMS Capstone) | **Submission Date:** 26 November 2026

---

## 1. How to Run Everything From Scratch (In Order)

### Prerequisites
- **MySQL 8.0** (running on `localhost:3306`) & `mysql.exe`
- **MongoDB** (local service `MongoDB` running on `localhost:27017`, or MongoDB Atlas URI)
- **Python 3.10+** (verified on Python 3.14.2)

### Step 1 — Configure `.env` and Python Virtual Environment
```powershell
# Copy .env.example to .env and fill in MYSQL_PASSWORD (and MONGO_URI if using Atlas)
copy .env.example .env

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r app\requirements.txt pymongo python-docx python-pptx
```

### Step 2 — Load Core MySQL Database (`01`–`05`)
Run in MySQL Workbench (or `mysql.exe`) in this exact order:
1. `sql-commands/01_ddl.sql` — creates `smart_office` and 13 InnoDB tables.
2. `sql-commands/02_data.sql` — loads ~743 sample rows (Nov 2–27, 2026).
3. `sql-commands/03_queries_views_indexes.sql` — runs 19 queries, 3 views, 2 indexes + `EXPLAIN`.
4. `sql-commands/04_triggers_procedures_functions.sql` — creates `booking_audit`, 3 triggers, 2 functions, 4 procedures.
5. `sql-commands/05_transactions_concurrency_demo.sql` — runs transaction & 2-session concurrency/deadlock demos.

### Step 3 — RBAC & Security (T1)
```powershell
Get-Content "sql-commands\06_rbac_security.sql" -Raw | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -h localhost -P 3306 -u root -p
.\.venv\Scripts\python.exe sql-commands\06_rbac_test.py
```
Output saved to `sql-commands/06_rbac_test_output.txt`.

### Step 4 — SQL Injection Demo (T2)
```powershell
.\.venv\Scripts\python.exe 07_sql_injection_demo.py
```
Output saved to `07_sql_injection_output.txt`.

### Step 5 — MongoDB NoSQL Extension (T3)
Ensure the `MongoDB` Windows service is running (`Start-Service MongoDB` as Administrator), then:
```powershell
.\.venv\Scripts\python.exe 08_mongodb\export_from_mysql.py
.\.venv\Scripts\python.exe 08_mongodb\mongo_demo.py
```
Output saved to `08_mongodb/mongo_demo_output.txt`. (Optional `mongosh` equivalent: `08_mongodb/mongosh_demo.js`.)

### Step 6 — Flask Web Application (T4)
```powershell
.\.venv\Scripts\python.exe app\app.py
```
Open `http://127.0.0.1:5000` in your browser.

### Step 7 — Automated Test Suite (T5)
```powershell
.\.venv\Scripts\python.exe 09_tests\run_tests.py
```
Outputs `09_tests/test_results.csv` and `09_tests/test_results.md` (22/22 PASS, cleans up all test rows).

---

## 2. Deliverables Map (Project 3 Brief → Files, Report & Screenshots)

| Brief Deliverable | File(s) in Workspace | Report Section | Screenshot |
|---|---|---|---|
| Requirements & business rules (BR1–BR14) | `DBMS_Capstone_Report_Final.docx` | Phase 1 | N/A (tables in Phase 1) |
| ER / EER diagram & relational schema | `smart_office_ER_diagram.drawio`, `sql-commands/01_ddl.sql` | Phase 2 & 3 | `screenshots/smart_office_ER_diagram.drawio.png` (embedded) |
| Functional dependencies & normalization (3NF/BCNF) | `DBMS_Capstone_Report_Final.docx` | Phase 3 | N/A (FD tables in Phase 3) |
| SQL scripts & realistic dataset (10+ tables, 200+ rows) | `sql-commands/01_ddl.sql`, `02_data.sql`, `generate_data.py` | Phase 4.1–4.2, Appendix A | `screenshots/SQL scripts + schema.png`, `quick-constraint-test.png`, `Dataset.png` (embedded) |
| Complex SQL query set (joins, subqueries, set ops, CTEs, windows) | `sql-commands/03_queries_views_indexes.sql` | Phase 4.3, Appendix B | Embedded in Phase 4 |
| Views, indexes, triggers, procedures, functions | `sql-commands/03_queries_views_indexes.sql`, `04_triggers_procedures_functions.sql` | Phase 4.4–4.5, Phase 5.1, Appendix C | `screenshots/04_triggers_procedures_functions.png` (embedded) |
| Transaction & two-session concurrency demo | `sql-commands/05_transactions_concurrency_demo.sql` | Phase 5.4–5.6, Appendix D | Covered in Phase 5 & `TC22` |
| RBAC & SQL-injection prevention demo | `sql-commands/06_rbac_security.sql`, `06_rbac_test.py`, `07_sql_injection_demo.py` | Phase 6, Appendix E & F | `[SCREENSHOT NEEDED]` (see `screenshot_checklist.md` #1 & #2) |
| NoSQL (MongoDB) + Application integration (CO4) | `08_mongodb/*`, `app/*` | Phase 7, Appendix G & H | `[SCREENSHOT NEEDED]` (see `screenshot_checklist.md` #3 & #4) |
| Testing (20+ cases: positive, negative, integrity, tx, concurrency) | `09_tests/run_tests.py`, `test_results.csv`, `test_results.md` | Phase 8, Appendix I | `[SCREENSHOT NEEDED]` (see `screenshot_checklist.md` #5) |
| Final report, presentation & viva prep | `DBMS_Capstone_Report_Final.docx`, `DBMS_Capstone_Presentation.pptx`, `viva_qa.md` | Entire Report | All above |
