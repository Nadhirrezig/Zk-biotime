"""Assign punches to shift instances.

punch_state is never recorded, so in/out is inferred:
1. Punches are grouped into clusters (repeated taps within `duplicate_window_min`).
2. Each cluster is tried as the arrival of a shift instance (absorbing the following
   clusters that still belong to it) or as the departure of an instance with no arrival.
3. An option that yields a complete pair wins. Otherwise the nearest shift boundary wins;
   on an exact tie (contiguous rotations: 14:00 ends one shift and starts the next) the
   shift the employee works on neighbouring days wins, and failing that the departure.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from typing import Callable

from .models import Rules, ShiftDef


@dataclass(frozen=True)
class Cluster:
    times: tuple[datetime, ...]

    @property
    def first(self) -> datetime:
        return self.times[0]

    @property
    def last(self) -> datetime:
        return self.times[-1]


@dataclass(frozen=True)
class ShiftInstance:
    day: date
    shift: ShiftDef
    start: datetime
    end: datetime
    window_start: datetime
    window_end: datetime


@dataclass(frozen=True)
class Assignment:
    instance: ShiftInstance
    clusters: tuple[Cluster, ...]
    arrival_missing: bool

    @property
    def is_complete(self) -> bool:
        return not self.arrival_missing and len(self.clusters) >= 2


ContextFn = Callable[[datetime], "str | None"]


def cluster_punches(times: list[datetime], window_min: int) -> list[Cluster]:
    """Group sorted punches: a punch within `window_min` of its cluster's first punch
    is a duplicate tap."""
    window = timedelta(minutes=window_min)
    clusters: list[list[datetime]] = []
    for t in times:
        if clusters and t - clusters[-1][0] <= window:
            clusters[-1].append(t)
        else:
            clusters.append([t])
    return [Cluster(tuple(c)) for c in clusters]


def build_instance(day: date, shift: ShiftDef, tz: tzinfo, rules: Rules) -> ShiftInstance:
    start = datetime.combine(day, shift.start, tzinfo=tz)
    end_day = day + timedelta(days=1) if shift.crosses_midnight else day
    end = datetime.combine(end_day, shift.end, tzinfo=tz)
    return ShiftInstance(
        day=day,
        shift=shift,
        start=start,
        end=end,
        window_start=start - timedelta(minutes=rules.window_before_start_min),
        window_end=end + timedelta(minutes=rules.window_after_end_min),
    )


def _following(clusters: list[Cluster], i: int, inst: ShiftInstance,
               instances: list[ShiftInstance]) -> int:
    """How many clusters after clusters[i] still belong to `inst`: inside its window and
    not closer to the start of a later shift than to this shift's end."""
    anchor = clusters[i].first
    later_starts = [o.start for o in instances
                    if o is not inst and o.start > anchor and o.start > inst.start]
    count = 0
    for cluster in clusters[i + 1:]:
        t = cluster.last
        if t > inst.window_end:
            break
        to_end = abs(t - inst.end)
        if any(abs(t - s) < to_end for s in later_starts):
            break
        count += 1
    return count


def assign(
    clusters: list[Cluster],
    instances: list[ShiftInstance],
    context: ContextFn | None = None,
) -> tuple[list[Assignment], list[Cluster]]:
    """Return (assignments, orphan clusters outside every window)."""
    instances = sorted(instances, key=lambda inst: inst.start)
    used: set[int] = set()
    assignments: list[Assignment] = []
    orphans: list[Cluster] = []

    def ctx_penalty(inst: ShiftInstance, t: datetime) -> int:
        if context is None:
            return 0
        code = context(t)
        return 0 if code is None or code == inst.shift.code else 1

    i = 0
    while i < len(clusters):
        cluster = clusters[i]
        best = None  # (key, idx, arrival_missing, taken)
        for idx, inst in enumerate(instances):
            if idx in used:
                continue
            if inst.window_start <= cluster.first <= inst.end:
                taken = _following(clusters, i, inst, instances)
                dist = abs(cluster.first - inst.start)
                if taken:
                    key = (0, dist, 0, 0)
                else:
                    key = (1, dist, ctx_penalty(inst, cluster.first), 1)
                if best is None or key < best[0]:
                    best = (key, idx, False, taken)
            if inst.start <= cluster.last <= inst.window_end:
                taken = _following(clusters, i, inst, instances)
                dist = abs(cluster.last - inst.end)
                key = (1, dist, ctx_penalty(inst, cluster.last), 0)
                if best is None or key < best[0]:
                    best = (key, idx, True, taken)
        if best is None:
            orphans.append(cluster)
            i += 1
            continue
        _, idx, arrival_missing, taken = best
        used.add(idx)
        assignments.append(
            Assignment(instances[idx], tuple(clusters[i:i + 1 + taken]), arrival_missing)
        )
        i += 1 + taken
    return assignments, orphans


def neighbour_context(assignments: list[Assignment]) -> ContextFn | None:
    """Shift code of the employee's nearest complete shift, used to break ties."""
    complete = sorted((a.instance.start, a.instance.shift.code)
                      for a in assignments if a.is_complete)
    if not complete:
        return None
    starts = [s for s, _ in complete]

    def lookup(t: datetime) -> str | None:
        pos = bisect_left(starts, t)
        candidates = [complete[j] for j in (pos - 1, pos) if 0 <= j < len(complete)]
        return min(candidates, key=lambda c: abs(c[0] - t))[1]

    return lookup


def pair_punches(
    times: list[datetime], instances: list[ShiftInstance], rules: Rules
) -> tuple[list[Assignment], list[Cluster]]:
    clusters = cluster_punches(sorted(times), rules.duplicate_window_min)
    first_pass, _ = assign(clusters, instances)
    context = neighbour_context(first_pass)
    if context is None:
        return assign(clusters, instances)
    return assign(clusters, instances, context)
