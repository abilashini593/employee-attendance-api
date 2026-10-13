# Employee Attendance & Analytics API

A robust FastAPI backend for employee attendance tracking, manual regularization with audit logging, and reporting powered by native MongoDB aggregation pipelines and optimized indexes.

## Tech Stack
- **Framework:** FastAPI, Pydantic v2
- **Database:** MongoDB (Motor / PyMongo) with native Aggregation Framework
- **Runtime:** Python 3.11+

## Core Features
- **Employee Lifecycle Management:** Role, department, and profile tracking.
- **Attendance & Punch Lifecycle:** Automated punch-in/out, work hour calculations, half-day flagging, and leave management.
- **Regularization & Auditing:** Manual attendance overrides with a full historical audit trail.
- **Advanced Analytics:** Monthly employee summaries, department totals, late leaderboards, and time-series department trends (featuring `$densify` gap-filling and 7-day moving averages).

## Database Performance & Optimization
All aggregation pipelines and endpoints have been fully verified using MongoDB explain plans (`/admin/explain/{endpoint}`), ensuring:
- **Zero Slow Collection Scans:** 100% index coverage across high-frequency queries.
- **Optimized Composite Indexes:** Leveraging custom indexes like `emp_code_1_date_1`, `date_1_late_minutes_1_emp_code_1`, and `department_1_joined_on_1`.

## Local Setup

### 1. Environment & Dependencies
Create and activate a virtual environment, then install dependencies:
```bash
# On Linux / macOS
python -m venv .venv && source .venv/bin/activate

# On Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt

2. Configure MongoDB
Ensure MongoDB is running locally (e.g. via local service or Docker):

docker run -d -p 27017:27017 --name mongodb mongo:7

Optional: create a .env file (environment variables override defaults):

MONGO_URI=mongodb://localhost:27017
MONGO_DB=attendance_db

3. Seed Sample Data
Load initial employee and attendance records:

python sample_seed.py

4. Run the API Server
Start the FastAPI server:

uvicorn app.main:app --port 8000 --reload

Interactive Swagger docs: http://localhost:8000/docs

Health check: http://localhost:8000/health

Running Tests
Run the automated test suite covering all business rules, endpoints, and edge cases:

pytest test_suite.py -v

Repository Structure
app/main.py: Complete application code including endpoints, business rules, helpers, and aggregation pipelines.

requirements.txt: Python package dependencies.

sample_seed.py: Loads sample Extended JSON datasets into MongoDB.

DATA_MODEL.md: Schema definition and specification of stored documents.

REVIEW.md: Comprehensive review and defect analysis of starter code.

DECISIONS.md: Design rationale for indexes, concurrency safety, competition ranking, and scalability.

openapi.yaml: Formal OpenAPI 3.0.3 contract.