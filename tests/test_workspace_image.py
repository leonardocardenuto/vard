"""Run against a migrated test database: TEST_DATABASE_URL=... python -m unittest discover -s tests -p test_workspace_image.py."""
import os
import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.models import AppUser
from api.routers.workspaces import create_workspace, get_workspace, list_workspaces, update_workspace
from api.schemas import WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate


@unittest.skipUnless(os.getenv('TEST_DATABASE_URL'), 'Requires a migrated test database')
class WorkspaceImageTest(unittest.TestCase):
    def test_create_replace_preserve_and_remove_image(self):
        engine = create_engine(os.environ['TEST_DATABASE_URL'])
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
                    user = AppUser(email=f'image-{uuid.uuid4().hex}@example.com')
                    session.add(user)
                    session.flush()
                    image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aCWQAAAAASUVORK5CYII='
                    workspace = create_workspace(WorkspaceCreate(name='Photo test', slug=f'photo-{uuid.uuid4().hex}', image_url=image), session, user)
                    workspace_id = workspace.id
                    session.expire_all()
                    loaded = get_workspace(workspace_id, session, user)
                    self.assertEqual(WorkspaceResponse.model_validate(loaded).image_url, image)
                    self.assertEqual(list_workspaces(session, user)[0].image_url, image)
                    update_workspace(workspace_id, WorkspaceUpdate(name='Renamed'), session, user)
                    session.expire_all()
                    self.assertEqual(get_workspace(workspace_id, session, user).image_url, image)
                    replacement = image + '\n'
                    update_workspace(workspace_id, WorkspaceUpdate(image_url=replacement), session, user)
                    session.expire_all()
                    self.assertEqual(get_workspace(workspace_id, session, user).image_url, replacement)
                    update_workspace(workspace_id, WorkspaceUpdate(image_url=None), session, user)
                    session.expire_all()
                    self.assertIsNone(get_workspace(workspace_id, session, user).image_url)
            finally:
                transaction.rollback()
        engine.dispose()
