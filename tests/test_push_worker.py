from contextlib import nullcontext
from types import SimpleNamespace

from api.services.push import PushWorker


def test_busy_worker_drains_full_batches_without_sleeping(monkeypatch):
    worker = PushWorker()
    waits = []
    closed = []
    calls = []
    def process(db):
        calls.append(db)
        return len(calls) <= 21
    def wait(timeout):
        waits.append(timeout)
        if timeout:
            worker.stop_event.set()
    listener = SimpleNamespace(wait=wait, close=lambda: closed.append(True))
    monkeypatch.setattr('api.services.push.PushListener', lambda: listener)
    monkeypatch.setattr('api.services.push.SessionLocal', SimpleNamespace(begin=lambda: nullcontext(None)))
    monkeypatch.setattr('api.services.push.process_one', process)
    monkeypatch.setattr('api.services.push.close_push_transport', lambda: closed.append('http'))
    worker.run()
    assert waits == [0, 0, 2]
    assert len(calls) == 22
    assert closed == [True, 'http']


def test_missing_listener_falls_back_to_scanning_the_outbox(monkeypatch):
    worker = PushWorker()
    calls = []
    def unavailable():
        raise RuntimeError('private database details')
    def fallback(timeout):
        calls.append(timeout)
        worker.stop_event.set()
    monkeypatch.setattr('api.services.push.PushListener', unavailable)
    monkeypatch.setattr('api.services.push.SessionLocal', SimpleNamespace(begin=lambda: nullcontext(None)))
    monkeypatch.setattr('api.services.push.process_one', lambda db: calls.append('scan') or False)
    monkeypatch.setattr(worker.stop_event, 'wait', fallback)
    monkeypatch.setattr('api.services.push.close_push_transport', lambda: None)
    worker.run()
    assert calls == ['scan', 2]
