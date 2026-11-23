from app.material import example
from app.modules.compose.reconcile import reconcile
from app.modules.compose.service import conflicts
from app.pipeline import inspect

# 门铃只响在一句对白中间：对白 D1 占 [1001,2002)，音效 S1 只占 [1402,1602)
ORIGINALS = dict(
    cues='cue_id,track,format,in,out,text\nD1,对白,FRAME,1250,2500,我们改天再谈\nS1,音效,FRAME,1750,2000,门铃响了\n',
    cuts='cut,start,end,target,kind\nK,0,10000,0,KEEP\n')


def doorbell():
    kept = [dict(track='对白', cue_id='D1', line=2, frame_in=1001, frame_out=2002),
            dict(track='音效', cue_id='S1', line=3, frame_in=1402, frame_out=1602)]
    rows = [dict(seg=1, frame_in=1001, frame_out=1402, parts=[dict(track='对白', cue_id='D1')]),
            dict(seg=2, frame_in=1402, frame_out=1602,
                 parts=[dict(track='对白', cue_id='D1'), dict(track='音效', cue_id='S1')]),
            dict(seg=3, frame_in=1602, frame_out=2002, parts=[dict(track='对白', cue_id='D1')])]
    return kept, rows


def test_doorbell_merges_only_while_ringing():
    stage = inspect(ORIGINALS)['compose']
    assert [(row['frame_in'], row['frame_out'], row['cues']) for row in stage['rows']] == [
        (1001, 1402, ['D1']), (1402, 1602, ['D1', 'S1']), (1602, 2002, ['D1'])]
    chime = next(row for row in stage['rows'] if 'S1' in row['cues'])
    assert (chime['frame_in'], chime['frame_out']) == (1402, 1602)
    assert chime['text'] == '我们改天再谈\n门铃响了'
    assert chime['parts'] == [dict(cue_id='D1', line=2, track='对白'),
                              dict(cue_id='S1', line=3, track='音效')]


def test_doorbell_reconciles_clean():
    stage = inspect(ORIGINALS)['compose']
    assert stage['counts'] == dict(segments=3, merged=1, frames=1001, cues=2)
    assert stage['conflicts']['counts'] == dict(regions=0, overlap_frames=0)
    assert stage['reconcile']['counts'] == dict(cues=2, missing=0, early=0, duplicated=0)


def test_clean_sample_merges_dialogue_and_effect():
    stage = inspect(example('clean'))['compose']
    merged, = [row for row in stage['rows'] if row['merged']]
    assert (merged['cues'], merged['lines'], merged['frame_in'], merged['frame_out']) == \
        (['C03', 'C04'], [4, 5], 801, 882)
    assert stage['counts'] == dict(segments=3, merged=1, frames=153, cues=4)


def test_dirty_sample_projection():
    stage = inspect(example('dirty'))['compose']
    assert stage['counts'] == dict(segments=20, merged=7, frames=594, cues=14)
    assert stage['conflicts']['counts'] == dict(regions=0, overlap_frames=0)
    assert stage['reconcile']['counts'] == dict(cues=14, missing=0, early=0, duplicated=0)
    triple = next(row for row in stage['rows'] if len(row['cues']) == 3)
    assert (triple['frame_in'], triple['frame_out'], triple['lines']) == (855, 883, [2, 3, 17])


def test_missing_content_detected():
    kept, rows = doorbell()
    report = reconcile(kept, rows[:1] + rows[2:])
    assert report['counts']['missing'] == 400
    assert {(row['cue_id'], row['missing']) for row in report['rows']} == {('D1', 200), ('S1', 200)}


def test_early_hint_detected():
    kept, rows = doorbell()
    rows[1] = dict(seg=2, frame_in=1001, frame_out=2002,
                   parts=[dict(track='对白', cue_id='D1'), dict(track='音效', cue_id='S1')])
    report = reconcile(kept, rows)
    row, = [row for row in report['rows'] if row['cue_id'] == 'S1']
    assert (row['line'], row['early']) == (3, 801)
    assert report['counts']['early'] == 801


def test_duplicated_content_detected():
    kept, rows = doorbell()
    rows.append(dict(seg=4, frame_in=1402, frame_out=1602, parts=[dict(track='音效', cue_id='S1')]))
    assert reconcile(kept, rows)['counts']['duplicated'] == 200
    assert conflicts(rows)['counts'] == dict(regions=1, overlap_frames=200)


def test_export_tracks_original_lines(client):
    run = client.post('/api/runs', json={'sample': 'clean'}).json
    package = client.get(f"/api/delivery/{run['id']}/export").json
    merged, = [row for row in package['stages']['compose']['rows'] if row['merged']]
    assert merged['parts'] == [dict(cue_id='C03', line=4, track='简中'),
                               dict(cue_id='C04', line=5, track='英语')]
    assert merged['lines'] == [4, 5]


def test_rerun_same_originals_adds_no_record(client):
    first = client.post('/api/runs', json=ORIGINALS).json
    again = client.post('/api/runs', json=ORIGINALS).json
    assert again['reused'] and again['id'] == first['id']
    assert client.get('/api/runs').json['count'] == 1


def test_compose_api(client):
    result = client.get('/api/check/compose?sample=clean')
    assert result.json['counts'] == dict(segments=3, merged=1, frames=153, cues=4)


def test_compose_post_api(client):
    result = client.post('/api/check/compose', json=ORIGINALS)
    assert [row['cues'] for row in result.json['rows']] == [['D1'], ['D1', 'S1'], ['D1']]


def test_compose_sheet(client):
    run = client.post('/api/runs', json=ORIGINALS).json
    html = client.get(f"/sheet/compose?run={run['id']}").get_data(as_text=True)
    assert '合成放映' in html and '门铃响了' in html
