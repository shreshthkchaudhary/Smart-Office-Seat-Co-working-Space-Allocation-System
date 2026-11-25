"""
08_mongodb/export_from_mysql.py
Task T3 (Step 1): Export workspace catalog & amenities from MySQL (smart_office)
into flexible JSON documents (08_mongodb/workspace_config.json) for MongoDB.
Connects using low-privilege emp_5 (which has SELECT on catalog tables).
"""

import json
import os
from pathlib import Path
import mysql.connector
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

OUT_JSON = Path(__file__).resolve().parent / "workspace_config.json"


def main():
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_EMP_USER", "emp_5"),
        password=os.getenv("MYSQL_EMP_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "smart_office"),
    )
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT r.resource_id, r.resource_code, r.resource_type, r.status,
               z.zone_name, f.floor_no, o.office_name, o.city,
               d.desk_number, d.desk_type,
               rm.room_name, rm.capacity
        FROM resource r
        JOIN zone z   ON z.zone_id   = r.zone_id
        JOIN floor f  ON f.floor_id  = z.floor_id
        JOIN office o ON o.office_id = f.office_id
        LEFT JOIN desk d  ON d.resource_id  = r.resource_id
        LEFT JOIN room rm ON rm.resource_id = r.resource_id
        ORDER BY r.resource_id
    """)
    resources = cur.fetchall()

    cur.execute("""
        SELECT ra.resource_id, a.amenity_name
        FROM resource_amenity ra
        JOIN amenity a ON a.amenity_id = ra.amenity_id
        ORDER BY ra.resource_id, a.amenity_name
    """)
    amenity_map: dict[int, list[str]] = {}
    for row in cur.fetchall():
        amenity_map.setdefault(row["resource_id"], []).append(row["amenity_name"])

    cur.close()
    conn.close()

    docs = []
    for r in resources:
        rid = r["resource_id"]
        amenities = amenity_map.get(rid, [])

        # Base document shared by all resources
        doc: dict = {
            "resource_id": rid,
            "resource_code": r["resource_code"],
            "resource_type": r["resource_type"],
            "status": r["status"],
            "location": {
                "office": r["office_name"],
                "city": r["city"],
                "floor_no": r["floor_no"],
                "zone": r["zone_name"],
            },
            "amenities": amenities,
        }

        # Flexible, type-specific fields (varies per desk vs room!)
        if r["resource_type"] == "Desk":
            doc["desk_number"] = r["desk_number"]
            doc["layout"] = {
                "desk_type": r["desk_type"],
                "orientation": "Window" if rid % 2 == 0 else "Interior",
                "power_outlets": 2 if r["desk_type"] == "Standing" else 1,
            }
            doc["equipment"] = [a for a in amenities] + (
                ["Adjustable Sit-Stand Frame"] if r["desk_type"] == "Standing" else []
            )
            doc["sensor_info"] = {
                "occupancy_sensor": f"PIR-{r['resource_code']}",
                "noise_zone_db": 42 if r["desk_type"] == "Quiet" else 55,
            }
        else:
            cap = r["capacity"]
            doc["room_name"] = r["room_name"]
            doc["capacity"] = cap
            doc["layout"] = {
                "seating_style": "Boardroom" if cap >= 12 else "Huddle",
                "reconfigurable": cap >= 20,
            }
            doc["equipment"] = amenities
            doc["accessibility"] = {
                "wheelchair_accessible": True,
                "hearing_loop": cap >= 20,
            }
            doc["sensor_info"] = {
                "co2_ppm_threshold": 1000,
                "smart_thermostat": True,
                "av_controller_ip": f"10.20.{r['floor_no']}.{100 + rid}",
            }

        docs.append(doc)

    OUT_JSON.write_text(json.dumps(docs, indent=2), encoding="utf-8")
    print(f"Exported {len(docs)} workspace_config documents to {OUT_JSON}")


if __name__ == "__main__":
    main()
