"""Select isolated storage before any test module imports the application."""
import os,tempfile
os.environ['ASTER_DATA_DIR']=tempfile.mkdtemp(prefix='aster-suite-')

import pytest
@pytest.fixture(autouse=True)
def isolate_quiz_reviewer(request,monkeypatch):
    if request.node.path.name=='test_quiz_audit.py':return
    from src import quizzes
    async def reviewed(questions):pass
    monkeypatch.setattr(quizzes,'audit_questions',reviewed)
