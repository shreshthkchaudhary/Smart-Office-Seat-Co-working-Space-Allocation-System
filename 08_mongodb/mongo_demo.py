"""
08_mongodb/mongo_demo.py
Task T3 (Step 2): Import workspace_config.json into MongoDB, create indexes,
demonstrate CRUD (insert, find, update, delete) and 2+ aggregation pipelines.
Reads MONGO_URI and MONGO_DB from .env (works locally or on MongoDB Atlas).
"""

import json
import os
from pathlib import Path
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "smart_office_nosql")
JSON_PATH = Path(__file__).resolve().parent / "workspace_config.json"
OUT_FILE = Path(__file__).resolve().parent / "mongo_demo_output.txt"


def main():
    lines = []
    lines.append("=" * 72)
    lines.append("SMART OFFICE MONGODB (NoSQL) EXTENSION DEMO")
    lines.append(f"Database: {MONGO_DB} | Collection: workspace_config")
    lines.append("=" * 72)

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
    client.admin.command("ping")
    db = client[MONGO_DB]
    col = db["workspace_config"]

    # 1. Import from MySQL export
    docs = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    col.delete_many({})
    col.insert_many(docs)
    lines.append(f"\n[1. IMPORT] Loaded {col.count_documents({})} documents from workspace_config.json")

    # 2. Create Indexes
    col.create_index([("resource_code", ASCENDING)], unique=True, name="idx_resource_code_unique")
    col.create_index([("amenities", ASCENDING)], name="idx_amenities_multikey")
    lines.append("[2. INDEXES] Created unique index 'idx_resource_code_unique' and multikey 'idx_amenities_multikey'")

    # 3. CRUD Operations
    lines.append("\n[3. CRUD OPERATIONS]")
    # CREATE
    temp_doc = {
        "resource_id": 999,
        "resource_code": "T-999",
        "resource_type": "Room",
        "status": "Active",
        "location": {"office": "Gurugram HQ", "city": "Gurugram", "floor_no": 3, "zone": "Innovation Pod"},
        "room_name": "Temp VR Pod",
        "capacity": 6,
        "amenities": ["4K Display", "VR Headset"],
        "accessibility": {"wheelchair_accessible": True},
    }
    col.insert_one(temp_doc)
    lines.append("  INSERT: Inserted temporary document resource_code='T-999'")

    # READ
    large_rooms = list(
        col.find(
            {"resource_type": "Room", "capacity": {"$gte": 20}},
            {"_id": 0, "resource_code": 1, "room_name": 1, "capacity": 1, "location.city": 1},
        )
    )
    lines.append(f"  FIND (Rooms with capacity >= 20): {len(large_rooms)} found -> {large_rooms}")

    # UPDATE
    col.update_one(
        {"resource_code": "T-999"},
        {"$set": {"status": "Maintenance"}, "$push": {"amenities": "Acoustic Panels"}},
    )
    updated = col.find_one({"resource_code": "T-999"}, {"_id": 0, "resource_code": 1, "status": 1, "amenities": 1})
    lines.append(f"  UPDATE (T-999): {updated}")

    # DELETE (cleanup temporary test doc)
    del_res = col.delete_one({"resource_code": "T-999"})
    lines.append(f"  DELETE (T-999 cleanup): deleted_count={del_res.deleted_count}")

    # 4. Aggregation Pipelines
    lines.append("\n[4. AGGREGATION PIPELINE 1: Count of Resources by Amenity]")
    pipe_amenities = [
        {"$unwind": "$amenities"},
        {"$group": {"_id": "$amenities", "resource_count": {"$sum": 1}}},
        {"$sort": {"resource_count": -1, "_id": 1}},
    ]
    for row in col.aggregate(pipe_amenities):
        lines.append(f"  {row['_id']:<25} -> {row['resource_count']} resources")

    lines.append("\n[5. AGGREGATION PIPELINE 2: Average Room Capacity per City & Floor]")
    pipe_capacity = [
        {"$match": {"resource_type": "Room"}},
        {
            "$group": {
                "_id": {"city": "$location.city", "floor_no": "$location.floor_no"},
                "room_count": {"$sum": 1},
                "avg_capacity": {"$avg": "$capacity"},
                "max_capacity": {"$max": "$capacity"},
            }
        },
        {"$sort": {"_id.city": 1, "_id.floor_no": 1}},
    ]
    for row in col.aggregate(pipe_capacity):
        loc = row["_id"]
        lines.append(
            f"  {loc['city']} Floor {loc['floor_no']}: "
            f"rooms={row['room_count']}, avg_cap={row['avg_capacity']:.1f}, max_cap={row['max_capacity']}"
        )

    output_text = "\n".join(lines) + "\n"
    OUT_FILE.write_text(output_text, encoding="utf-8")
    print(output_text)
    print(f"Saved output to: {OUT_FILE}")
    client.close()


if __name__ == "__main__":
    main()
