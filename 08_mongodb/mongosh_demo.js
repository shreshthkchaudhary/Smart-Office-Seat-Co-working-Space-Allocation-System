// ============================================================================
// 08_mongodb/mongosh_demo.js
// Task T3: mongosh equivalent script for MongoDB Compass / mongosh shell.
// Run after importing workspace_config.json (or via mongo_demo.py):
//   mongosh "mongodb://localhost:27017/smart_office_nosql" 08_mongodb/mongosh_demo.js
// ============================================================================

use("smart_office_nosql");

// 1. Index creation
db.workspace_config.createIndex({ resource_code: 1 }, { unique: true, name: "idx_resource_code_unique" });
db.workspace_config.createIndex({ amenities: 1 }, { name: "idx_amenities_multikey" });

// 2. CRUD: Insert
db.workspace_config.insertOne({
  resource_id: 999,
  resource_code: "T-999",
  resource_type: "Room",
  status: "Active",
  location: { office: "Gurugram HQ", city: "Gurugram", floor_no: 3, zone: "Innovation Pod" },
  room_name: "Temp VR Pod",
  capacity: 6,
  amenities: ["4K Display", "VR Headset"],
  accessibility: { wheelchair_accessible: true }
});

// 3. CRUD: Find
print("=== Rooms with capacity >= 20 ===");
printjson(
  db.workspace_config.find(
    { resource_type: "Room", capacity: { $gte: 20 } },
    { _id: 0, resource_code: 1, room_name: 1, capacity: 1, "location.city": 1 }
  ).toArray()
);

// 4. CRUD: Update
db.workspace_config.updateOne(
  { resource_code: "T-999" },
  { $set: { status: "Maintenance" }, $push: { amenities: "Acoustic Panels" } }
);
print("=== Updated T-999 ===");
printjson(db.workspace_config.findOne({ resource_code: "T-999" }, { _id: 0 }));

// 5. CRUD: Delete (cleanup)
db.workspace_config.deleteOne({ resource_code: "T-999" });

// 6. Aggregation Pipeline 1: Count resources by amenity
print("=== Aggregation 1: Count by Amenity ===");
printjson(
  db.workspace_config.aggregate([
    { $unwind: "$amenities" },
    { $group: { _id: "$amenities", resource_count: { $sum: 1 } } },
    { $sort: { resource_count: -1, _id: 1 } }
  ]).toArray()
);

// 7. Aggregation Pipeline 2: Average room capacity per city & floor
print("=== Aggregation 2: Average Room Capacity per City & Floor ===");
printjson(
  db.workspace_config.aggregate([
    { $match: { resource_type: "Room" } },
    {
      $group: {
        _id: { city: "$location.city", floor_no: "$location.floor_no" },
        room_count: { $sum: 1 },
        avg_capacity: { $avg: "$capacity" },
        max_capacity: { $max: "$capacity" }
      }
    },
    { $sort: { "_id.city": 1, "_id.floor_no": 1 } }
  ]).toArray()
);
