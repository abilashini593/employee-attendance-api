import os
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

# Point to test database
os.environ["MONGO_URI"] = "mongodb://localhost:27017"
os.environ["MONGO_DB"] = "attendance_test_db"

from app.main import app, db, init_indexes, round_half_up, get_attendance_date, compute_late_minutes, compute_work_hours, compute_overtime

client = TestClient(app)


@pytest.fixture(autouse=True, scope="module")
def setup_database():
    # Initialize indexes and clean collections
    init_indexes()
    db.employees.delete_many({})
    db.attendance_logs.delete_many({})

    # Seed baseline employees
    employees = [
        {
            "emp_code": "EMP0001",
            "name": "Asha Rao",
            "email": "asha@example.com",
            "department": "Engineering",
            "shift_start": "09:30",
            "shift_end": "18:30",
            "joined_on": "2026-01-05",
            "created_at": datetime(2026, 1, 5, 4, 30, tzinfo=timezone.utc),
        },
        {
            "emp_code": "EMP0002",
            "name": "Vikram Shah",
            "email": "vikram@example.com",
            "department": "Engineering",
            "shift_start": "09:30",
            "shift_end": "18:30",
            "joined_on": "2026-07-13",
            "created_at": datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc),
        },
        {
            "emp_code": "EMP0003",
            "name": "Neha Iyer",
            "email": "neha@example.com",
            "department": "Sales",
            "shift_start": "09:30",
            "shift_end": "18:30",
            "joined_on": "2026-02-01",
            "created_at": datetime(2026, 2, 1, 4, 0, tzinfo=timezone.utc),
        },
        {
            "emp_code": "EMP0005",
            "name": "David Miller",
            "email": "david@example.com",
            "department": "Support",
            "shift_start": "22:00",
            "shift_end": "06:00",
            "joined_on": "2026-03-01",
            "created_at": datetime(2026, 3, 1, 4, 0, tzinfo=timezone.utc),
        },
    ]
    db.employees.insert_many(employees)
    yield
    # Teardown
    db.employees.delete_many({})
    db.attendance_logs.delete_many({})


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_create_and_list_employees():
    emp_payload = {
        "emp_code": "EMP0010",
        "name": "Alice Green",
        "email": "alice@example.com",
        "department": "QA",
        "shift_start": "10:00",
        "shift_end": "19:00",
        "joined_on": "2026-06-01",
    }
    # Create employee
    res = client.post("/employees", json=emp_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["emp_code"] == "EMP0010"
    assert "_id" not in data
    assert isinstance(data["created_at"], int)

    # Duplicate emp_code -> 409
    res_dup = client.post("/employees", json=emp_payload)
    assert res_dup.status_code == 409

    # Equal shift_start and shift_end -> 422
    invalid_shift = emp_payload.copy()
    invalid_shift["emp_code"] = "EMP0011"
    invalid_shift["shift_end"] = "10:00"
    res_inv = client.post("/employees", json=invalid_shift)
    assert res_inv.status_code == 422

    # List employees
    res_list = client.get("/employees?department=QA")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] == 1
    assert list_data["items"][0]["emp_code"] == "EMP0010"


def test_punch_in_and_rules():
    # R2 Late rule: shift 09:30:
    # 09:40:00 -> 0
    # 09:40:01 -> 10
    # 10:15:59 -> 45
    d_str = "2026-07-06"
    shift_start = "09:30"
    dt_40_00 = datetime(2026, 7, 6, 4, 10, 0, tzinfo=timezone.utc)  # 09:40:00 IST
    dt_40_01 = datetime(2026, 7, 6, 4, 10, 1, tzinfo=timezone.utc)  # 09:40:01 IST
    dt_15_59 = datetime(2026, 7, 6, 4, 45, 59, tzinfo=timezone.utc) # 10:15:59 IST

    assert compute_late_minutes(dt_40_00, shift_start, d_str) == 0
    assert compute_late_minutes(dt_40_01, shift_start, d_str) == 10
    assert compute_late_minutes(dt_15_59, shift_start, d_str) == 45

    # R1 Overnight shift (22:00-06:00):
    # Punch in 2026-07-07 01:10 IST (before 06:00) belongs to 2026-07-06
    ms_overnight = int(datetime(2026, 7, 6, 19, 40, 0, tzinfo=timezone.utc).timestamp() * 1000)
    assert get_attendance_date(ms_overnight, "22:00", "06:00") == "2026-07-06"

    # API Punch-in
    # Asha Rao punch in at 09:28 IST (03:58 UTC) on 2026-07-06
    punch_in_ms = int(datetime(2026, 7, 6, 3, 58, 0, tzinfo=timezone.utc).timestamp() * 1000)
    res = client.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": punch_in_ms})
    assert res.status_code == 201
    rec = res.json()
    assert rec["date"] == "2026-07-06"
    assert rec["late_minutes"] == 0
    assert rec["punch_out"] is None
    assert rec["work_hours"] is None

    # Duplicate punch-in on same day -> 409
    res_dup = client.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": punch_in_ms})
    assert res_dup.status_code == 409


def test_punch_out_and_rules():
    # Asha Rao punch out at 18:35 IST (13:05 UTC) on 2026-07-06
    punch_out_ms = int(datetime(2026, 7, 6, 13, 5, 0, tzinfo=timezone.utc).timestamp() * 1000)
    res = client.post("/attendance/punch-out", json={"emp_code": "EMP0001", "punched_at": punch_out_ms})
    assert res.status_code == 200
    rec = res.json()
    assert rec["work_hours"] == 9.12
    assert rec["overtime_minutes"] == 0  # 5 min < 30 min minimum
    assert rec["half_day"] is False

    # Second punch-out -> 409 Conflict
    res_dup = client.post("/attendance/punch-out", json={"emp_code": "EMP0001", "punched_at": punch_out_ms})
    assert res_dup.status_code == 409


def test_regularize_and_audit():
    # Insert another record for Neha (EMP0003) on 2026-07-06: late 35 min
    in_ms = int(datetime(2026, 7, 6, 4, 35, 0, tzinfo=timezone.utc).timestamp() * 1000)
    out_ms = int(datetime(2026, 7, 6, 13, 40, 0, tzinfo=timezone.utc).timestamp() * 1000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0003", "punched_at": in_ms})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0003", "punched_at": out_ms})

    # HR regularizes Neha's punch_in to 09:28 IST (03:58 UTC)
    corrected_in_ms = int(datetime(2026, 7, 6, 3, 58, 0, tzinfo=timezone.utc).timestamp() * 1000)
    patch_payload = {
        "reason": "Biometric terminal glitch",
        "regularized_by": "hr.manager",
        "punch_in": corrected_in_ms,
    }
    res = client.patch("/attendance/EMP0003/2026-07-06", json=patch_payload)
    assert res.status_code == 200
    updated = res.json()
    assert updated["late_minutes"] == 0
    assert len(updated["history"]) == 1
    h = updated["history"][0]
    assert h["by"] == "hr.manager"
    assert "late_minutes" in h["changes"]
    assert h["changes"]["late_minutes"]["from"] == 35
    assert h["changes"]["late_minutes"]["to"] == 0

    # Sending same patch with no changes -> 422
    res_nochange = client.patch("/attendance/EMP0003/2026-07-06", json=patch_payload)
    assert res_nochange.status_code == 422


def test_analytics_and_explain():
    # Explain attendance_list
    res_exp1 = client.get("/admin/explain/attendance_list")
    assert res_exp1.status_code == 200
    exp1_data = res_exp1.json()
    assert exp1_data["endpoint"] == "attendance_list"
    assert exp1_data["collection"] == "attendance_logs"

    # Explain employee_monthly
    res_exp2 = client.get("/admin/explain/employee_monthly?emp_code=EMP0001&month=2026-07")
    assert res_exp2.status_code == 200
    exp2_data = res_exp2.json()
    assert exp2_data["endpoint"] == "employee_monthly"

    # Explain department_summary
    res_exp3 = client.get("/admin/explain/department_summary?month=2026-07")
    assert res_exp3.status_code == 200

    # Explain late_leaderboard
    res_exp4 = client.get("/admin/explain/late_leaderboard?month=2026-07")
    assert res_exp4.status_code == 200

    # Explain department_trend
    res_exp5 = client.get("/admin/explain/department_trend?department=Engineering&from=2026-07-01&to=2026-07-15")
    assert res_exp5.status_code == 200

    # Employee monthly analytics
    res_m = client.get("/analytics/employees/EMP0001/monthly?month=2026-07")
    assert res_m.status_code == 200
    m_data = res_m.json()
    assert m_data["emp_code"] == "EMP0001"
    assert m_data["working_days"] == 23
    assert m_data["present_days"] == 1.0

    # Department summary
    res_dept = client.get("/analytics/departments/summary?month=2026-07")
    assert res_dept.status_code == 200
    dept_data = res_dept.json()
    eng = next((d for d in dept_data["items"] if d["department"] == "Engineering"), None)
    assert eng is not None
    # Engineering headcount: EMP0001 joined Jan 2026, EMP0002 joined July 13 2026 -> 2
    assert eng["headcount"] == 2

    # Department trend
    res_trend = client.get("/analytics/departments/Engineering/trend?from=2026-07-01&to=2026-07-10")
    assert res_trend.status_code == 200
    trend_data = res_trend.json()
    # 10 calendar days returned
    assert len(trend_data["items"]) == 10
