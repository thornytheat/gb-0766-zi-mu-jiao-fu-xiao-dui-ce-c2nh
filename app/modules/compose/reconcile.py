from collections import defaultdict
from app.modules.overlaps.sweep import spans


def reconcile(kept, rows):
    mapped, lines = defaultdict(list), {}
    for fragment in kept:
        key = (fragment['track'], fragment['cue_id'])
        mapped[key].append((fragment['frame_in'], fragment['frame_out']))
        lines.setdefault(key, fragment['line'])
    projected = defaultdict(list)
    for row in rows:
        for part in row['parts']:
            projected[(part['track'], part['cue_id'])].append((row['frame_in'], row['frame_out']))
    problems, totals = [], dict(missing=0, early=0, duplicated=0)
    for key in sorted(set(mapped) | set(projected)):
        found = dict(missing=shortfall(mapped.get(key, []), projected.get(key, [])),
                     early=shortfall(projected.get(key, []), mapped.get(key, [])),
                     duplicated=doubled(projected.get(key, [])))
        for name, value in found.items():
            totals[name] += value
        if any(found.values()):
            problems.append(dict(track=key[0], cue_id=key[1], line=lines.get(key), **found))
    return dict(rows=problems, counts=dict(cues=len(set(mapped) | set(projected)), **totals))


def shortfall(base, cover):
    events = defaultdict(lambda: [0, 0])
    for left, right in base:
        if left < right:
            events[left][0] += 1
            events[right][0] -= 1
    for left, right in cover:
        if left < right:
            events[left][1] += 1
            events[right][1] -= 1
    total, depth, covered, previous = 0, 0, 0, None
    for point in sorted(events):
        if previous is not None and depth > 0 and covered == 0:
            total += point - previous
        delta = events[point]
        depth, covered = depth + delta[0], covered + delta[1]
        previous = point
    return total


def doubled(intervals):
    marked = [(left, right, mark) for mark, (left, right) in enumerate(intervals)]
    return sum(right - left for left, right, active in spans(marked) if len(active) > 1)
