import uuid

from sqlalchemy import text

from api.services.push_wakeup import PushListener, notify_push


def test_wakeup_is_delivered_only_after_commit_not_rollback(test_engine, monkeypatch):
    monkeypatch.setattr('api.services.push_wakeup.PUSH_CHANNEL', f'test_push_{uuid.uuid4().hex}')
    listener = PushListener()
    try:
        with test_engine.connect() as db:
            transaction = db.begin()
            notify_push(db)
            assert not listener.wait(.05)
            transaction.commit()
            assert listener.wait(1)
            assert not listener.wait(.05)
            transaction = db.begin()
            notify_push(db)
            transaction.rollback()
            assert not listener.wait(.05)
    finally:
        listener.close()
