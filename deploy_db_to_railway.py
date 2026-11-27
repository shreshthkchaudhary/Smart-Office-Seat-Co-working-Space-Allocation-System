"""
deploy_db_to_railway.py
Helper script to populate Railway MySQL with the Smart Office schema, data, views,
triggers, and stored procedures.

Usage:
  python deploy_db_to_railway.py
  (Prompts for Railway connection details, or reads from .env / CLI args)
"""

import os
import sys
import subprocess
from pathlib import Path
from urllib.parse import urlparse
import mysql.connector

ROOT_DIR = Path(__file__).resolve().parent
MYSQL_EXE = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"


def parse_connection_info():
    """Extract connection parameters from URL or individual prompts/env."""
    url = os.getenv("RAILWAY_MYSQL_URL", "").strip()
    if not url and len(sys.argv) > 1 and sys.argv[1].startswith("mysql://"):
        url = sys.argv[1]

    if url:
        p = urlparse(url)
        return {
            "host": p.hostname,
            "port": p.port or 3306,
            "user": p.username or "root",
            "password": p.password or "",
            "database": p.path.lstrip("/") or "railway",
        }

    # Fallback to individual variables
    host = os.getenv("RAILWAY_MYSQL_HOST") or os.getenv("MYSQLHOST")
    port = os.getenv("RAILWAY_MYSQL_PORT") or os.getenv("MYSQLPORT")
    user = os.getenv("RAILWAY_MYSQL_USER") or os.getenv("MYSQLUSER") or "root"
    password = os.getenv("RAILWAY_MYSQL_PASSWORD") or os.getenv("MYSQLPASSWORD")
    database = os.getenv("RAILWAY_MYSQL_DATABASE") or os.getenv("MYSQLDATABASE") or "railway"

    if not host or not password:
        print("\n=== Railway MySQL Connection Setup ===")
        print("Tip: In Railway MySQL -> 'Connect' tab -> copy the 'Public Networking' details or MySQL URL.\n")
        raw_input_val = input("Enter Railway MySQL Connection URL (or press Enter to type details manually): ").strip()
        if raw_input_val.startswith("mysql://"):
            p = urlparse(raw_input_val)
            return {
                "host": p.hostname,
                "port": p.port or 3306,
                "user": p.username or "root",
                "password": p.password or "",
                "database": p.path.lstrip("/") or "railway",
            }
        host = input("Railway MySQL Host (e.g. roundhouse.proxy.rlwy.net): ").strip()
        port = input("Railway MySQL Port (e.g. 12345): ").strip()
        user = input("Railway MySQL User [default: root]: ").strip() or "root"
        password = input("Railway MySQL Password: ").strip()
        database = input("Railway MySQL Database [default: railway]: ").strip() or "railway"

    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "database": database,
    }


def execute_sql_file_via_client(cfg: dict, sql_path: Path):
    """Execute SQL file using mysql.exe to preserve DELIMITER, triggers, and multi-queries."""
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    print(f"-> Executing {sql_path.name}...")
    
    # Read file content and replace `USE smart_office;` if target DB is different
    content = sql_path.read_text(encoding="utf-8")
    if cfg["database"] != "smart_office":
        content = content.replace("USE smart_office;", f"USE `{cfg['database']}`;")
        content = content.replace("smart_office.", f"`{cfg['database']}`.")

    cmd = [
        MYSQL_EXE,
        f"-h{cfg['host']}",
        f"-P{cfg['port']}",
        f"-u{cfg['user']}",
        f"-p{cfg['password']}",
        cfg["database"],
    ]

    proc = subprocess.run(cmd, input=content, text=True, capture_output=True, encoding="utf-8")
    if proc.returncode != 0:
        print(f"Error executing {sql_path.name}:\n{proc.stderr}")
        return False
    return True


def main():
    cfg = parse_connection_info()
    print(f"\nConnecting to Railway MySQL at {cfg['host']}:{cfg['port']} (Database: {cfg['database']})...")

    # 1. Test basic connection
    try:
        conn = mysql.connector.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            connect_timeout=15,
        )
        cur = conn.cursor()
        cur.execute("SELECT VERSION()")
        ver = cur.fetchone()[0]
        print(f"Connected successfully! MySQL Version: {ver}\n")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    # 2. Run SQL scripts in order
    scripts = [
        ROOT_DIR / "sql-commands" / "01_ddl.sql",
        ROOT_DIR / "sql-commands" / "02_data.sql",
        ROOT_DIR / "sql-commands" / "03_queries_views_indexes.sql",
        ROOT_DIR / "sql-commands" / "04_triggers_procedures_functions.sql",
    ]

    for s in scripts:
        ok = execute_sql_file_via_client(cfg, s)
        if not ok:
            print(f"Migration aborted at {s.name}.")
            sys.exit(1)
        print(f"✓ {s.name} completed successfully.")

    # 3. Verify counts
    print("\nVerifying migrated table counts on Railway...")
    conn = mysql.connector.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
    )
    cur = conn.cursor(dictionary=True)
    for tbl in ["resource", "employee", "booking", "cancellation", "access_log"]:
        cur.execute(f"SELECT COUNT(*) as c FROM `{tbl}`")
        cnt = cur.fetchone()["c"]
        print(f"  • {tbl}: {cnt} rows")

    cur.close()
    conn.close()

    print("\n=======================================================")
    print("SUCCESS: Railway MySQL is fully populated and verified!")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
