from app.modules.overlaps.service import locate
from app.modules.overlaps.sweep import spans
from .reconcile import reconcile

TRACK = '放映'


def compose(fragments):
    kept = [row for row in fragments if row['kind'] == 'KEEP' and row['frame_in'] < row['frame_out']]
    rows = project(kept)
    return dict(rows=rows, conflicts=conflicts(rows), reconcile=reconcile(kept, rows),
                counts=dict(segments=len(rows), merged=sum(row['merged'] for row in rows),
                            frames=sum(row['frames'] for row in rows),
                            cues=len({(part['track'], part['cue_id']) for row in rows for part in row['parts']})))


def project(kept):
    intervals = [(row['frame_in'], row['frame_out'], mark) for mark, row in enumerate(kept)]
    rows = []
    for left, right, active in spans(intervals):
        parts = sorted((kept[mark] for mark in active), key=lambda row: (row['track'], row['line'], row['cue_id']))
        rows.append(dict(seg=len(rows) + 1, track=TRACK, frame_in=left, frame_out=right, frames=right - left,
                         text='\n'.join(row['text'] for row in parts),
                         cues=[row['cue_id'] for row in parts], lines=[row['line'] for row in parts],
                         parts=[dict(cue_id=row['cue_id'], line=row['line'], track=row['track']) for row in parts],
                         merged=len(parts) > 1))
    return rows


def conflicts(rows):
    screen = [dict(kind='KEEP', track=TRACK, frame_in=row['frame_in'], frame_out=row['frame_out'],
                   line=row['seg'], cue_id=str(row['seg'])) for row in rows]
    return locate(screen)
