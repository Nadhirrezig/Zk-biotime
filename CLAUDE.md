# CLAUDE.md: ZKBio Time attendance dashboard

## Objective
A Windows desktop app (Python + **PyQt6**, **French UI**) that reads attendance data
from a client's **ZKBio Time 9** database and produces attendance reporting:
employee records, daily/monthly attendance, anomalies, statistics, PDF/Excel exports.
Key user need: filter employees who **punched twice (in + out)** vs **only once**,
plus lateness, early departure, absences and worked hours.

## Context (how we got here)
- The ZKBio Time **API could not be used**, so we read the **PostgreSQL database directly**.
- ZKBio Time server: Windows VM. PostgreSQL **15.14**, database `biotime`, port **7496**,
  user `postgres`. Auth is `trust` for localhost only.
- Dev access from the host goes through a Windows port forward on the VM:
  `192.168.10.6:7497 -> 127.0.0.1:7496` (script `zk-host-access.ps1`, `-Remove` to undo).
- Editing `postgresql.conf` / `pg_hba.conf` by hand once **broke the client's server**.
  **Never modify server config or ZKBio files.** Remote-PC access comes later (Stage 4) via a
  tested script that creates a read-only user.
- Raw query outputs from the exploration session are in `docs/`
  (`columns.txt`, `checks.txt`, `rahma.txt`).

## Hard rules
- **Read-only** on the ZKBio DB. Open every connection with
  `options="-c default_transaction_read_only=on -c TimeZone=Africa/Tunis"`.
- **Nothing hard-coded:** connection, time zone, shifts, schedules, rules, holidays,
  exclusions and refresh interval all live in app settings.
- App-owned data (settings, shifts, schedules, holidays, leave, overrides) goes in
  **local SQLite**. The DB password is stored with `keyring`, not in SQLite.
- UI text in French. Code and comments in English.
- Queries and calculations run in `QThread` workers. The UI never blocks.
- **Auto refresh** with a `QTimer` (interval set in settings).

## Critical data findings
1. **Time zone.** The DB server's `TimeZone` is `Asia/Shanghai` (+08), but the device has
   `terminal_tz = 1` (UTC+1). Stored timestamps are correct moments in time:
   **always convert to `Africa/Tunis`**. ZKBio Time's own reports already match that.
   Example: Rahma's departure `2026-09-02 00:03+08` is `2026-09-01 17:03` in Tunis.
   Windows needs the `tzdata` pip package for `zoneinfo`.
2. **`punch_state` is always 255.** The device never records in/out, so it must be inferred.
3. **Night shifts cross midnight** (22–06, 18–06). Never group punches by calendar date;
   **pair them per shift instance.**
4. **ZKBio Time schedules are unusable:** 1 shift with no time slots, assigned only for
   August 2026. Schedules come from our own config.
5. **`att_payloadbase` is empty** (ZKBio Time never calculated attendance): we compute it ourselves.
6. **`att_leave` and `att_holiday` are empty:** our app manages leave and holidays.
7. **`is_active` is false for everyone.** That field is the mobile-app login, not employment.
   Employed = not listed in `personnel_resign`.
8. Exclude `emp_code 1` ("Admin" test account). 5 employees have empty or partial names.
9. Dataset: 24 real employees, 3,227 punches, 1 device (`UFS2252600345`, "IP OFF SHORE").
   Punches run from 2026-07-14 to **2026-10-30 08:54 Tunis**, when the device stopped
   sending. The UI must allow picking any date, not only today.

## Table map
- Employees: `personnel_employee` (id, emp_code, first_name, last_name, department_id,
  position_id, hire_date), `personnel_department` (dept_name), `personnel_resign`.
- Punches: `iclock_transaction` (emp_id, emp_code, punch_time, terminal_sn,
  terminal_alias, verify_type, is_attendance), `iclock_terminal`. Also `att_manuallog`.
- Unused or empty ZKBio data: `att_attshift`, `att_shiftdetail`, `att_timeinterval`,
  `att_attschedule`, `att_leave` (employee and approval status live in
  `workflow_workflowinstance`), `att_holiday`, `att_payloadbase`.

## Observed patterns (seed defaults only; client must confirm)
- **Production:** rotating 3×8: 06:00–14:00, 14:00–22:00, 22:00–06:00.
- **Administration:** Mon–Fri about 08:00/08:30–17:00, Saturday about 08:00–13:00,
  Sunday off. Summer (July–August) single session until about 14:00–15:00.
- **Gardiennage:** 18:00–06:00.
- Public holidays visible in the data: 25 July, 15 October. Seed Tunisia's fixed-date holidays.
- Pending client confirmations: official start times, tolerance, summer dates and hours,
  Saturday hours.

## Attendance engine
1. Load punches for the period (±1 day margin) and convert to Africa/Tunis.
2. Drop duplicates within `duplicate_window_min`.
3. Pick the shift for each employee and date from the department's schedule for that
   date (date-ranged periods: summer vs regular, weekday-specific hours).
   For rotating departments, auto-pick the shift whose start is nearest the first punch.
   A manual override table wins over both.
4. Assign punches to the shift window `[start - early_margin, end + late_margin]`
   (may cross midnight). Arrival = first punch, departure = last. Middle punches are ignored.
5. Status per shift-day:
   - `complet`: both arrival and departure
   - `pointage unique`: one punch; mark as missing arrival or missing departure, by proximity
   - `absent`: scheduled day, no punch, no leave, no holiday
   - `congé`, `férié`, `repos`
6. Metrics: late (with tolerance), early departure, worked hours, overtime (optional).
   Every threshold is configurable.

**Test case (Rahma, `emp_code 302`, Administration), expected results:**
- 1 Sep: departure 17:03 belongs to 1 Sep, not 2 Sep.
- 24 Sep: single punch, missing arrival.
- 25 Jul and 15 Oct: `férié`.
- 10–22 Aug: `absent` until leave is entered, then `congé`.
- 16 Jul: duplicates collapse to one arrival and one departure.
- Arrivals 17 Jul 11:03, 23 Jul 12:05, 3 Sep 09:45: late.

## Stages
**Stage 1: Foundation**
- Project skeleton and SQLite store.
- Settings dialog: connection with a test button, time zone, rules, refresh interval,
  seeded shifts and schedules editable in a basic form.
- Read-only DB layer.
- Attendance engine with unit tests (Rahma test case).
- Dashboard: today's or a chosen date's present / late / single punch / absent counts.
- Daily attendance view with filters: twice / once / absent / late.
- Auto refresh.

**Stage 2: Analysis**
- Employee record with punch history.
- Anomalies screen.
- Monthly statistics: days worked, absences, total lateness, hours.

**Stage 3: Management and exports**
- Full editors for shifts, schedules, holidays, leave and overrides.
- Excel export (`openpyxl`) and PDF export (`QPdfWriter` / `QTextDocument`) from any table.

**Stage 4: Deployment**
- PyInstaller build.
- Tested script to create a read-only DB user with a password, and to allow LAN access
  for app instances on other PCs. Never use the dev port forward with `trust` on the
  client's network.

## Stack
PyQt6, `psycopg[binary]` (v3), `tzdata`, `keyring`, `openpyxl`, `pytest`.
Tables use `QTableView` + `QAbstractTableModel` + `QSortFilterProxyModel`.
## Decisions (session 2, Stage 1 build)
- The agency runs 24/7 and cannot provide official hours: every shift, schedule, tolerance
  and window stays editable in **Paramètres**. Seeds are the observed patterns above.
- **Days off are per department**: a schedule period lists working weekdays; uncovered
  days are `repos`. Scheduled day without punches = `absent` (no rota for Production).
- **Late minutes** default to `arrival − (start + tolerance)` (setting `late_mode`,
  alternative `from_start`).
- **Leave**: engine supports it (`compute(..., leaves=)`), but there is **no leave UI/table**
  in Stage 1 (client asked to keep the app simple). Holidays have full CRUD.
- **Holidays seeded**: fixed Tunisian dates as recurring + 2026 lunar dates as one-off
  "(date à confirmer)". Mouled 2026-08-25 matches Rahma's unexplained absence.
- **Pairing** (`engine/pairing.py`): punches → duplicate clusters → shift instances.
  Complete pair wins; else nearest shift boundary. In contiguous rotations (06/14/22) a
  lone punch is always equidistant, so ties use the employee's nearest complete shift
  (neighbour context), then fall back to "departure". Lone punches are highlighted.
- Punches outside every window are reported as `unscheduled` ("Hors planning").
- Dev container cannot reach 192.168.10.6: tests use `tests/fixtures/rahma_punches.csv`
  (built by `tools/build_rahma_fixture.py`) and `tests/fakes.py`.

## Decisions (session 3, client feedback: "keep it basic")
- The client group wants **basic reporting only**. Screens show: pointage double, pointage
  unique, absents, total pointés (= double + unique), per-employee period stats, Excel/PDF
  export and printing. No rate, lateness, early departure, hours or overtime on screen.
- The engine still computes lateness/hours (tests unchanged); the UI just does not show them.
  Lateness/overtime settings are hidden from Paramètres but kept in SQLite.
- Two tabs: **Journée** (date, 4 cards, list with filters, double-click → employee) and
  **Employé** (employee + period, 4 day counts, day-by-day list).
- Exports use what is on screen (filters + sort): `src/zkreport/export.py` (Excel, HTML),
  `ui/table_export.py` (PDF via QPrinter, print dialog).

## Code map
- `src/zkreport/engine/`: pure Python (guarded by `tests/test_engine_purity.py`).
- `src/zkreport/store/`: SQLite settings (`settings_store.py`, seeds in `seed.py`), keyring.
- `src/zkreport/db/`: psycopg read-only connection + SELECT-only repository.
- `src/zkreport/service.py`: load one day / one employee over a period (DB → engine), no Qt.
- `src/zkreport/ui/`: PyQt6 (main window, dashboard, daily view, settings, QThread jobs).
  Colours live in `ui/theme.py` (light theme only, Fusion style). Pages: `daily_page.py`,
  `employee_page.py`; shared `results_table.py`, `stat_cards.py` (4 cards = table filters).
- Run: `python -m zkreport`. Tests: `pytest` (UI tests run with `QT_QPA_PLATFORM=offscreen`).
