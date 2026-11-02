import pytest
from src import store,library,document_viewer

@pytest.fixture(autouse=True)
def workspace(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);library.init()

def seed():
    store.save_material('course:post','MRK','Leksioni 1','Post description','https://classroom.google.com/post')
    store.save_material('course:deck','MRK','Prezantim.pptx','Full lesson content','https://drive.google.com/deck')
    store.set_setting('attachments:course:post',['course:deck','course:deck'])

def test_post_and_attachment_are_one_visible_section():
    seed();catalog=store.material_catalog()
    visible=[m for m in catalog if not m.get('hidden_in_library')]
    assert len(visible)==1
    assert visible[0]['title']=='Leksioni 1'
    assert len(visible[0]['attachments'])==1
    assert 'Full lesson content' in visible[0]['body']
    assert 'Prezantim.pptx' in visible[0]['search_text']
    assert len(store.rows('materials'))==2

def test_multiple_documents_stay_in_same_section_on_repeated_scans():
    seed()
    store.save_material('course:doc','MRK','Exercises.pdf','Questions','')
    for _ in range(2):
        store.set_setting('attachments:course:post',['course:deck','course:doc'])
        store.save_material('course:deck','MRK','Prezantim.pptx','Updated content','')
    visible=[m for m in store.material_catalog() if not m.get('hidden_in_library')]
    assert len(visible)==1 and len(visible[0]['attachments'])==2
    assert 'Updated content' in visible[0]['body']
    with pytest.raises(ValueError,match='Choose an attached'):document_viewer.original('course:post')

def test_identical_titles_do_not_merge_unrelated_posts():
    seed();store.save_material('other:post','Other class','Leksioni 1','Other content','')
    assert len([m for m in store.material_catalog() if not m.get('hidden_in_library')])==2

def test_grouping_does_not_change_completion_or_quiz_source():
    seed();store.save_task('course:deck','MRK','Question to answer','Review',None)
    task=store.rows('tasks')[0];store.toggle(task['id'],True)
    store.material_catalog()
    assert store.rows('tasks')[0]['done']==1
    assert store.rows('tasks')[0]['source_id']=='course:deck'
