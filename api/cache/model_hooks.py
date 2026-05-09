from sqlalchemy import event
from sqlalchemy.orm import Session

from api.cache.response_cache import get_response_cache
from api.models import (
    AppUser,
    Camera,
    Notification,
    NotificationChannel,
    NotificationDelivery,
    UserCredential,
    Workspace,
    WorkspaceInvite,
    WorkspaceMember,
)

SESSION_CACHE_TAGS_KEY = "cache_invalidation_tags"

CACHE_TAGS_BY_MODEL = {
    AppUser: ("users", "workspaces"),
    UserCredential: ("users",),
    Workspace: ("workspaces", "workspace_members", "cameras", "notifications", "invites"),
    WorkspaceMember: ("workspaces", "workspace_members", "users"),
    WorkspaceInvite: ("invites", "workspace_members"),
    Camera: ("cameras", "notifications"),
    Notification: ("notifications",),
    NotificationChannel: ("notifications", "users"),
    NotificationDelivery: ("notifications",),
}


def register_cache_invalidation_hooks() -> None:
    if event.contains(Session, "before_flush", collect_cache_tags_before_flush):
        return

    event.listen(Session, "before_flush", collect_cache_tags_before_flush)
    event.listen(Session, "after_commit", invalidate_cache_tags_after_commit)
    event.listen(Session, "after_rollback", clear_cache_tags_after_rollback)


def collect_cache_tags_before_flush(session: Session, *_args) -> None:
    tags = session.info.setdefault(SESSION_CACHE_TAGS_KEY, set())
    changed_instances = tuple(session.new) + tuple(session.dirty) + tuple(session.deleted)
    for instance in changed_instances:
        tags.update(cache_tags_for_instance(instance))


def invalidate_cache_tags_after_commit(session: Session) -> None:
    tags = session.info.pop(SESSION_CACHE_TAGS_KEY, set())
    if tags:
        get_response_cache().invalidate_tags(*tags)


def clear_cache_tags_after_rollback(session: Session) -> None:
    session.info.pop(SESSION_CACHE_TAGS_KEY, None)


def cache_tags_for_instance(instance: object) -> tuple[str, ...]:
    for model_type, tags in CACHE_TAGS_BY_MODEL.items():
        if isinstance(instance, model_type):
            return tags
    return ()
