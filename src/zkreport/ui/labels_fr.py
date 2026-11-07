"""French UI labels."""
from zkreport.engine.models import DayResult, Missing, Status

STATUS = {
    Status.COMPLETE: "Pointage double",
    Status.SINGLE_PUNCH: "Pointage unique",
    Status.ABSENT: "Absent",
    Status.LEAVE: "Congé",
    Status.HOLIDAY: "Férié",
    Status.REST: "Repos",
}

MISSING = {
    Missing.NONE: "",
    Missing.ARRIVAL: "arrivée manquante",
    Missing.DEPARTURE: "départ manquant",
}

WEEKDAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

FILTER_ALL = "all"
FILTER_PRESENT = "present"   # double + single
FILTER_TWICE = "twice"
FILTER_ONCE = "once"
FILTER_ABSENT = "absent"

FILTERS = [
    (FILTER_ALL, "Tous"),
    (FILTER_TWICE, "Pointage double"),
    (FILTER_ONCE, "Pointage unique"),
    (FILTER_ABSENT, "Absents"),
    (FILTER_PRESENT, "Pointés (double + unique)"),
]
FILTER_LABELS = dict(FILTERS)


def status_text(r: DayResult) -> str:
    text = STATUS[r.status]
    details = []
    if r.missing is not Missing.NONE:
        details.append(MISSING[r.missing])
    if r.unscheduled:
        details.append("hors planning")
    if r.holiday_name and r.status is not Status.HOLIDAY:
        details.append(f"férié : {r.holiday_name}")
    if r.status is Status.HOLIDAY and r.holiday_name:
        details.append(r.holiday_name)
    return f"{text} ({', '.join(details)})" if details else text


def weekdays_label(days) -> str:
    """[0, 1, 2, 3, 4] -> 'Lun–Ven'; [0, 2, 5] -> 'Lun, Mer, Sam'."""
    days = sorted(days)
    if days == list(range(7)):
        return "Tous les jours"
    groups: list[list[int]] = []
    for d in days:
        if groups and d == groups[-1][-1] + 1:
            groups[-1].append(d)
        else:
            groups.append([d])
    parts = [WEEKDAYS[g[0]] if len(g) == 1
             else f"{WEEKDAYS[g[0]]}, {WEEKDAYS[g[1]]}" if len(g) == 2
             else f"{WEEKDAYS[g[0]]}–{WEEKDAYS[g[-1]]}" for g in groups]
    return ", ".join(parts) or "Aucun"


def employee_label(name: str, emp_code: str) -> str:
    return name or f"Sans nom (matricule {emp_code})"
