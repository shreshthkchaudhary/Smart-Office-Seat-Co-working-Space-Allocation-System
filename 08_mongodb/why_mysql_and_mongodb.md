# Why MySQL for Bookings and MongoDB for Flexible Configuration

In our Smart Office Seat & Co-working Space Allocation System, **MySQL 8.0 (InnoDB)** and **MongoDB** are used together (polyglot persistence) because each solves a different problem cleanly:

1. **Why MySQL for Core Bookings & Access Control:**
   - Reservations require strict **ACID transactions** and **row-level locking (`SELECT ... FOR UPDATE`)** so two employees cannot book the same desk or room for overlapping times (BR5).
   - Relational **foreign keys, CHECK constraints, triggers, and stored procedures** enforce business rules (such as room capacity BR6, active status BR7, max duration BR12, and 15-minute check-in windows BR10) reliably at the database level.

2. **Why MongoDB for Flexible Workspace Configuration (`workspace_config`):**
   - Desks and meeting rooms have **varying, evolving metadata** that does not fit a rigid table without many `NULL` columns or extra join tables: a standing desk has power outlets and noise-zone dB sensors, while a large conference room has seating style, reconfigurability, wheelchair/hearing-loop accessibility flags, CO₂ thresholds, and AV controller IPs.
   - MongoDB stores each workspace's full configuration as a single self-contained **JSON/BSON document** with nested objects and arrays, making it easy to add new IoT sensor fields or equipment types without `ALTER TABLE` migrations, while supporting fast **multikey indexing** and **aggregation pipelines** for facility reporting.
