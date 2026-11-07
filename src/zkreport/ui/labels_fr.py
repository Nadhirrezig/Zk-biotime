"""French UI labels."""
from zkreport.engine.models import LateMode, Missing, Status

STATUS = {
    Status.COMPLETE: "Complet",
    Status.SINGLE_PUNCH: "Pointage unique",
    Status.ABSENT: "Absent",
    Status.LEAVE: "Congé",
    Status.HOLIDAY: "Férié",
    Status.REST: "Repos",
}

MISSING = {
    Missing.NONE: "",
    Missing.ARRIVAL: "Arrivée manquante",
    Missing.DEPARTURE: "Départ manquant",
}

LATE_MODE = {
    LateMode.AFTER_TOLERANCE: "Après la tolérance (retard = arrivée − (début + tolérance))",
    LateMode.FROM_START: "Depuis l'heure de début (retard = arrivée − début)",
}

WEEKDAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

FILTER_ALL = "all"
FILTER_PRESENT = "present"
FILTER_TWICE = "twice"
FILTER_ONCE = "once"
FILTER_ABSENT = "absent"
FILTER_LATE = "late"

FILTERS = [
    (FILTER_ALL, "Tous"),
    (FILTER_PRESENT, "Présents"),
    (FILTER_TWICE, "Deux pointages (complet)"),
    (FILTER_ONCE, "Un seul pointage"),
    (FILTER_ABSENT, "Absents"),
    (FILTER_LATE, "En retard"),
]


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


def minutes_hm(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}" if minutes else ""


def employee_label(name: str, emp_code: str) -> str:
    return name or f"Sans nom (matricule {emp_code})"
