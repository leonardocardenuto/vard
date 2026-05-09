from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from typing import Any

from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.responses import Response as StarletteResponse

from api.core.config import get_settings
from api.core.security import TokenError, decode_access_token

try:
    from redis import Redis, RedisError
except ModuleNotFoundError:
    Redis = None
    RedisError = Exception

KEY_PREFIX = "response_cache:"
RESPONSE_PREFIX = f"{KEY_PREFIX}response:"
TAG_PREFIX = f"{KEY_PREFIX}tag:"
TAG_SCOPE_PREFIX = f"{KEY_PREFIX}tag_scope:"
TAG_SCOPES_PREFIX = f"{KEY_PREFIX}tag_scopes:"
DEFAULT_SCOPE_VALUE = "global"


class CacheScope(StrEnum):
    GLOBAL = "global"
    USER = "user"
    WORKSPACE = "workspace"


@dataclass(frozen=True)
class CachePolicy:
    key: str
    ttl_seconds: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)
    scope: CacheScope = CacheScope.USER
    include_query: bool = True
    include_path_params: bool = True
    key_parts: Callable[[Request], dict[str, Any]] | None = None


def cache_response(policy: CachePolicy):
    def decorator(endpoint):
        setattr(endpoint, "_cache_policy", policy)
        return endpoint

    return decorator


class CachedAPIRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def cached_route_handler(request: Request) -> Response:
            policy = getattr(self.endpoint, "_cache_policy", None)
            cache = get_response_cache()
            if request.method != "GET" or policy is None or not cache.enabled:
                return await original_route_handler(request)

            cache_key = cache.build_key(request, policy)
            cached_entry = cache.get(cache_key)
            if cached_entry is not None:
                return cached_entry.to_response(cache_key)

            response = await original_route_handler(request)
            if cache.is_cacheable_response(response):
                response = await materialize_response(response)
                response.headers["X-Response-Cache"] = "MISS"
                cache.maybe_expose_key(response, cache_key)
                cache.set(cache_key, response, policy, request)
            return response

        return cached_route_handler


@dataclass
class CacheEntry:
    status_code: int
    content_type: str
    body: bytes

    def to_response(self, cache_key: str) -> StarletteResponse:
        response = StarletteResponse(
            content=self.body,
            status_code=self.status_code,
            media_type=None,
        )
        if self.content_type:
            response.headers["content-type"] = self.content_type
        response.headers["X-Response-Cache"] = "HIT"
        get_response_cache().maybe_expose_key(response, cache_key)
        return response


class ResponseCache:
    def __init__(self, client: Redis | None) -> None:
        self.client = client

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def build_key(self, request: Request, policy: CachePolicy) -> str:
        payload: dict[str, Any] = {
            "key": policy.key.strip(),
            "scope": policy.scope.value,
            "actor": self.scope_value(request, policy),
        }

        parts: dict[str, Any] = {}
        if policy.include_path_params:
            parts["path"] = {key: str(value) for key, value in sorted(request.path_params.items())}
        if policy.include_query:
            parts["query"] = {key: request.query_params.getlist(key) for key in sorted(request.query_params)}
        if policy.key_parts is not None:
            parts["custom"] = policy.key_parts(request)
        if parts:
            payload["parts"] = parts

        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return RESPONSE_PREFIX + hashlib.sha256(raw).hexdigest()

    def get(self, key: str) -> CacheEntry | None:
        if not self.client:
            return None
        try:
            raw = self.client.get(key)
        except RedisError:
            return None
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            return CacheEntry(
                status_code=int(payload["status_code"]),
                content_type=str(payload.get("content_type") or ""),
                body=str(payload.get("body") or "").encode("latin1"),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def set(self, key: str, response: Response, policy: CachePolicy, request: Request) -> None:
        if not self.client:
            return

        body = getattr(response, "body", b"")
        if not isinstance(body, bytes):
            return

        payload = json.dumps(
            {
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "body": body.decode("latin1"),
            },
            separators=(",", ":"),
        )
        tags = normalize_tags(policy.tags)
        scope_value = self.scope_value(request, policy)

        try:
            pipe = self.client.pipeline(transaction=True)
            pipe.set(key, payload, ex=policy.ttl_seconds if policy.ttl_seconds > 0 else None)
            for tag in tags:
                tag_key = tag_redis_key(tag)
                scoped_tag_key = scoped_tag_redis_key(tag, policy.scope, scope_value)
                tag_scopes_key = tag_scopes_redis_key(tag)

                pipe.sadd(tag_key, key)
                pipe.sadd(scoped_tag_key, key)
                pipe.sadd(tag_scopes_key, scoped_tag_key)
                if policy.ttl_seconds > 0:
                    pipe.expire(tag_key, policy.ttl_seconds)
                    pipe.expire(scoped_tag_key, policy.ttl_seconds)
                    pipe.expire(tag_scopes_key, policy.ttl_seconds)
            pipe.execute()
        except RedisError:
            return

    def invalidate_tags(self, *tags: str) -> None:
        if not self.client:
            return

        for tag in normalize_tags(tags):
            tag_key = tag_redis_key(tag)
            tag_scopes_key = tag_scopes_redis_key(tag)
            try:
                keys = list(self.client.smembers(tag_key))
                scoped_tag_keys = list(self.client.smembers(tag_scopes_key))

                pipe = self.client.pipeline(transaction=True)
                if keys:
                    pipe.delete(*keys)
                pipe.delete(tag_key)
                if scoped_tag_keys:
                    pipe.delete(*scoped_tag_keys)
                pipe.delete(tag_scopes_key)
                pipe.execute()
            except RedisError:
                return

    def invalidate_scoped_tags(self, scope: CacheScope, scope_value: str, *tags: str) -> None:
        if not self.client:
            return

        for tag in normalize_tags(tags):
            scoped_tag_key = scoped_tag_redis_key(tag, scope, scope_value)
            try:
                keys = list(self.client.smembers(scoped_tag_key))
                pipe = self.client.pipeline(transaction=True)
                if keys:
                    pipe.delete(*keys)
                pipe.delete(scoped_tag_key)
                pipe.srem(tag_scopes_redis_key(tag), scoped_tag_key)
                pipe.execute()
            except RedisError:
                return

    def scope_value(self, request: Request | None, policy: CachePolicy) -> str:
        if policy.scope == CacheScope.GLOBAL:
            return DEFAULT_SCOPE_VALUE
        if request is None:
            return DEFAULT_SCOPE_VALUE
        if policy.scope == CacheScope.WORKSPACE:
            workspace_id = request.path_params.get("workspace_id") or request.query_params.get("workspace_id")
            if workspace_id:
                return str(workspace_id)
        if policy.scope == CacheScope.USER:
            user_id = user_id_from_request(request)
            if user_id:
                return user_id
        return DEFAULT_SCOPE_VALUE

    def is_cacheable_response(self, response: Response) -> bool:
        if response.status_code < 200 or response.status_code >= 300:
            return False
        return True

    def maybe_expose_key(self, response: Response, cache_key: str) -> None:
        if get_settings().app_env != "production":
            response.headers["X-Response-Cache-Key"] = cache_key


@lru_cache
def get_response_cache() -> ResponseCache:
    settings = get_settings()
    if Redis is None or not settings.redis_url:
        return ResponseCache(None)

    try:
        client = Redis.from_url(settings.redis_url, decode_responses=False)
        client.ping()
    except RedisError:
        return ResponseCache(None)

    return ResponseCache(client)


def user_id_from_request(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    try:
        payload = decode_access_token(token.strip())
    except TokenError:
        return None
    subject = payload.get("sub")
    return str(subject) if subject else None


async def materialize_response(response: Response) -> StarletteResponse:
    body = getattr(response, "body", None)
    if not isinstance(body, bytes):
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        body = b"".join(chunks)

    return StarletteResponse(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=None,
        background=response.background,
    )


def normalize_tags(tags: tuple[str, ...] | list[str]) -> list[str]:
    return sorted({tag.strip() for tag in tags if tag.strip()})


def tag_redis_key(tag: str) -> str:
    return TAG_PREFIX + tag.strip()


def scoped_tag_redis_key(tag: str, scope: CacheScope, scope_value: str) -> str:
    clean_scope_value = scope_value.strip() or DEFAULT_SCOPE_VALUE
    return f"{TAG_SCOPE_PREFIX}{scope.value}:{clean_scope_value}:{tag.strip()}"


def tag_scopes_redis_key(tag: str) -> str:
    return TAG_SCOPES_PREFIX + tag.strip()
