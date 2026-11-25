"""Generates 02_data.sql for the Smart Office database. Run: python generate_data.py"""
import random
from datetime import date, datetime, timedelta

random.seed(2026)          # same data every run
TODAY = date(2026, 11, 15)
NOW = datetime(2026, 11, 15, 12, 0)

def q(v):                  # SQL literal
    if v is None: return "NULL"
    if isinstance(v, (int, float)): return str(v)
    return "'" + str(v).replace("'", "''") + "'"

def insert(table, cols, rows):
    out = [f"INSERT INTO {table} ({', '.join(cols)}) VALUES"]
    out.append(",\n".join("  (" + ", ".join(q(x) for x in r) + ")" for r in rows) + ";\n")
    return "\n".join(out)

# ---------- master data ----------
departments = ["Engineering", "Human Resources", "Finance", "Marketing", "Sales", "Operations"]

first = ["Aarav","Vivaan","Aditya","Arjun","Rohan","Karan","Siddharth","Ishaan","Kabir","Yash",
         "Ananya","Diya","Priya","Neha","Kavya","Isha","Meera","Pooja","Riya","Sneha"]
last  = ["Sharma","Verma","Gupta","Singh","Mehta","Nair","Reddy","Iyer","Kapoor","Chauhan"]
employees = []
for i in range(40):
    n = f"{first[i % 20]} {last[(i * 3 + i // 20) % 10]}"
    email = n.lower().replace(" ", ".") + "@nexaworks.com"
    role = "Admin" if i < 2 else "Facility Manager" if i < 5 else "Security" if i < 7 else "Employee"
    phone = "9" + "".join(str(random.randint(0, 9)) for _ in range(9))
    employees.append((i + 1, n, email, phone, role, (i % 6) + 1))
assert len({e[2] for e in employees}) == 40

offices = [(1, "NexaWorks HQ", "Gurugram", "Sector 44, Gurugram, Haryana"),
           (2, "NexaWorks Tech Park", "Bengaluru", "Whitefield, Bengaluru, Karnataka")]
floors = [(1,1,1),(2,2,1),(3,3,1),(4,1,2),(5,2,2)]            # (id, floor_no, office_id)
zones = []
for fid in range(1, 6):
    zones += [(len(zones) + 1, "Zone A", fid), (len(zones) + 2, "Zone B", fid)]

# resources: 40 desks (ids 1-40, D-101..D-140) + 10 rooms (ids 41-50, R-201..R-210)
bad_status = {7: "Maintenance", 33: "Inactive", 49: "Maintenance"}
resources, desks, rooms = [], [], []
for i in range(1, 41):
    resources.append((i, f"D-{100 + i}", "Desk", bad_status.get(i, "Active"), (i - 1) // 4 + 1))
    dtype = "Standing" if i % 5 == 0 else "Quiet" if i % 7 == 0 else "Standard"
    desks.append((i, str(100 + i), dtype))
room_names = ["Alpha","Beta","Gamma","Delta","Sigma","Omega","Orion","Nova","Apollo","Zenith"]
room_caps  = [4, 6, 8, 10, 12, 20, 25, 30, 6, 8]
for j in range(10):
    rid = 41 + j
    resources.append((rid, f"R-{201 + j}", "Room", bad_status.get(rid, "Active"), j + 1))
    rooms.append((rid, room_names[j], room_caps[j]))

amenities = ["Monitor","Docking Station","Projector","Whiteboard","Video Conferencing",
             "Height-Adjustable Desk","Power Outlets","Printer Access"]
res_amen = []
for r in range(1, 41):
    s = {7}                                   # every desk has power outlets
    s.add(1 if r % 2 else 2)                  # monitor or docking station
    if r % 5 == 0: s.add(6)
    if r % 3 == 0: s.add(8)
    res_amen += [(r, a) for a in sorted(s)]
for r in range(41, 51):
    s = {3, 4, 7} | ({5} if room_caps[r - 41] >= 8 else set()) | ({8} if r % 2 else set())
    res_amen += [(r, a) for a in sorted(s)]

# ---------- bookings ----------
active_res = [r[0] for r in resources if r[3] == "Active"]
weight = {r: random.choice([1, 1, 2, 3]) for r in active_res}   # some resources are more popular
weekdays = [date(2026, 11, 1) + timedelta(d) for d in range(30)]
weekdays = [d for d in weekdays if d.weekday() < 5]

def t(h): return timedelta(hours=h)
START_W = {9:3, 9.5:2, 10:6, 10.5:5, 11:5, 12:2, 13:3, 14:6, 14.5:3, 15:4, 16:2}
busy_res, busy_emp = {}, {}

def free(book, key, d, s, e):
    return all(e <= s2 or s >= e2 for (s2, e2) in book.get((key, d), []))

def mark(book, key, d, s, e): book.setdefault((key, d), []).append((s, e))

bookings = []   # dicts

def add(emp, res, d, s, e, att, status, created):
    bookings.append(dict(emp=emp, res=res, date=d, s=s, e=e, att=att, status=status, created=created))
    if status != "Cancelled":
        mark(busy_res, res, d, s, e); mark(busy_emp, emp, d, s, e)

# fixed demo bookings (for the overlap / concurrency demo)
add(6, 2, date(2026,11,18), 10, 12, 1, "Confirmed", datetime(2026,11,12,9,0))      # Desk D-102, 10:00-12:00
add(9, 41, date(2026,11,18), 10, 12, 3, "Confirmed", datetime(2026,11,12,9,30))    # Room R-201, 10:00-12:00

TARGET = 270
tries = 0
while len(bookings) < TARGET and tries < 20000:
    tries += 1
    res = random.choices(active_res, weights=[weight[r] for r in active_res])[0]
    d = random.choice(weekdays)
    if d > date(2026, 11, 27): continue
    if res == 2 and d in (date(2026,11,18), date(2026,11,25)): continue    # keep D-102 free for demos
    is_room = res >= 41
    s = random.choices(list(START_W), weights=list(START_W.values()))[0]
    dur = random.choice([1,1,1.5,2,3,4]) if is_room else random.choice([2,4,4,6,8])
    e = s + dur
    if e > 19: continue
    cap = room_caps[res - 41] if is_room else 1
    att = random.randint(2, cap) if is_room else 1
    emp = random.randint(1, 40)
    past = d < TODAY
    # created_at: 1-7 days before, never in the future
    created = datetime.combine(d, datetime.min.time()) + t(s) - timedelta(days=random.randint(1, 7), hours=random.randint(0, 5))
    created = min(created, datetime(2026, 11, 15, 8, 0))
    r = random.random()
    if r < 0.12:
        status = "Cancelled"                              # cancelled ones free their slot
    else:
        if not (free(busy_res, res, d, s, e) and free(busy_emp, emp, d, s, e)): continue
        if past:
            nosh = 0.30 if emp in (12, 27) else 0.07
            status = "No-Show" if random.random() < nosh else "Completed"
        else:
            status = "Confirmed"
    add(emp, res, d, s, e, att, status, created)

bookings.sort(key=lambda b: (b["date"], b["s"], b["res"]))
for i, b in enumerate(bookings, 1): b["id"] = i

def tm(h): return f"{int(h):02d}:{int((h % 1) * 60):02d}:00"

booking_rows = [(b["id"], b["emp"], b["res"], b["date"].isoformat(), tm(b["s"]), tm(b["e"]),
                 b["att"], b["status"], b["created"].strftime("%Y-%m-%d %H:%M:%S")) for b in bookings]

reasons = ["Meeting rescheduled","Working from home","Plan changed","Booked by mistake",
           "Client visit postponed","Feeling unwell","Team offsite","Duplicate booking"]
cancel_rows, log_rows = [], []
for b in bookings:
    start_dt = datetime.combine(b["date"], datetime.min.time()) + t(b["s"])
    end_dt = datetime.combine(b["date"], datetime.min.time()) + t(b["e"])
    if b["status"] == "Cancelled":
        c = b["created"] + timedelta(hours=random.randint(1, 30))
        c = min(c, start_dt - timedelta(minutes=30), NOW)
        if c <= b["created"]: c = b["created"] + timedelta(hours=1)
        cancel_rows.append((len(cancel_rows) + 1, b["id"], c.strftime("%Y-%m-%d %H:%M:%S"), random.choice(reasons)))
    elif b["status"] == "Completed":
        ci = start_dt + timedelta(minutes=random.randint(-10, 12))
        co = end_dt + timedelta(minutes=random.randint(-40, 25))
        log_rows.append((len(log_rows) + 1, b["id"], ci.strftime("%Y-%m-%d %H:%M:%S"), co.strftime("%Y-%m-%d %H:%M:%S")))

# ---------- write file ----------
out = ["-- =====================================================",
       "-- 02_data.sql | Sample data for smart_office (run AFTER 01_ddl.sql)",
       "-- =====================================================",
       "USE smart_office;\n"]
out.append(insert("department", ["dept_id","dept_name"], list(enumerate(departments, 1))))
out.append(insert("employee", ["emp_id","name","email","phone","role","dept_id"], employees))
out.append(insert("office", ["office_id","office_name","city","address"], offices))
out.append(insert("floor", ["floor_id","floor_no","office_id"], floors))
out.append(insert("zone", ["zone_id","zone_name","floor_id"], zones))
out.append(insert("resource", ["resource_id","resource_code","resource_type","status","zone_id"], resources))
out.append(insert("desk", ["resource_id","desk_number","desk_type"], desks))
out.append(insert("room", ["resource_id","room_name","capacity"], rooms))
out.append(insert("amenity", ["amenity_id","amenity_name"], list(enumerate(amenities, 1))))
out.append(insert("resource_amenity", ["resource_id","amenity_id"], res_amen))
out.append(insert("booking", ["booking_id","emp_id","resource_id","booking_date","start_time","end_time","attendees","status","created_at"], booking_rows))
out.append(insert("cancellation", ["cancel_id","booking_id","cancelled_at","reason"], cancel_rows))
out.append(insert("access_log", ["log_id","booking_id","check_in_time","check_out_time"], log_rows))
open("/mnt/user-data/outputs/02_data.sql", "w", encoding="utf-8").write("\n".join(out))

counts = dict(department=6, employee=40, office=2, floor=5, zone=10, resource=50, desk=40, room=10,
              amenity=8, resource_amenity=len(res_amen), booking=len(booking_rows),
              cancellation=len(cancel_rows), access_log=len(log_rows))
print(counts, "TOTAL", sum(counts.values()))
