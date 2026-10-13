# DECISIONS.md

1. **Indexes.**
On `employees`:
- `{"emp_code": 1}` (unique): guarantees business code uniqueness and powers lookups.
- `{"department": 1, "emp_code": 1}`: powers filtered/sorted employee listing.
- `{"department": 1, "joined_on": 1}` & `{"joined_on": 1}`: powers department summary/trend filtering without collection scans.

On `attendance_logs`:
- `{"emp_code": 1, "date": 1}` (unique): enforces at most one record per employee per attendance day, guarantees race-safe punch-ins, and accelerates monthly summaries.
- `{"emp_code": 1, "punch_in": -1}`: optimizes finding the latest open punch-in for punch-outs.
- `{"date": -1, "emp_code": 1}`: enables fast paginated listing (`GET /attendance`).
- `{"date": 1, "late_minutes": 1, "emp_code": 1}`: powers the late leaderboard with covered index scans.

Rejected: an index on `history.at`, because regularization history is only read inline on individual records and never queried globally.

2. **Punch-in race.** Both requests validate input and compute the attendance date. Both attempt `insert_one`. Because `(emp_code, date)` has a unique index, MongoDB accepts the first insert and throws a `DuplicateKeyError` on the second. The API catches this error and returns HTTP 409. Exactly one request gets 201.

3. **Ties.** The pipeline uses standard competition ranking (`$rank` in `$setWindowFields`: 1, 2, 2, 4) and filters by `rank <= limit`. When employees tie at the cutoff rank, all tied employees are returned, sorted by `emp_code` ascending. Thus, responses may contain more than `limit` items.

4. **Headcount.** The aggregation originates from `employees` matching `joined_on <= month_end`, grouping by department to establish authoritative headcount (`$sum: 1`). Logs are fetched via `$lookup`; employees with zero logs still count toward headcount while contributing zero to attendance counts.

5. **One thing you would change for 100x data.** I would maintain pre-aggregated monthly employee attendance summaries and daily department rollups updated asynchronously via MongoDB Change Streams upon punch-out and regularization, replacing heavy multi-stage pipelines with $O(1)$ point lookups.
