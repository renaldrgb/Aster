from src import store

def test_only_classroom_coursework_with_due_date_is_assignment(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);store.init()
    store.save_task('upload:exercise','MRK','Draw a diagram','Homework','2026-11-06T12:00:00+00:00')
    practice=store.rows('tasks')[0];store.toggle(practice['id'],True)
    store.register_coursework('c:official','2026-11-06T12:00:00+00:00')
    store.save_task('c:official','MRK','Teacher assignment','Homework')
    store.register_coursework('c:undated',None)
    store.save_task('c:undated','MRK','Undated class activity','Homework')
    store.reclassify_tasks();tasks={t['source_id']:t for t in store.rows('tasks')}
    assert tasks['c:official']['kind']=='Homework' and tasks['c:official']['due']
    assert tasks['c:undated']['kind']=='Review'
    assert tasks['upload:exercise']['kind']=='Review' and tasks['upload:exercise']['due'] is None
    assert tasks['upload:exercise']['done']==1
    official=tasks['c:official'];store.toggle(official['id'],True)
    store.register_coursework('c:official',None)
    store.save_task('c:official','MRK','Teacher assignment','Homework')
    result=next(t for t in store.rows('tasks') if t['id']==official['id'])
    assert result['kind']=='Review' and result['due'] is None and result['done']==1
