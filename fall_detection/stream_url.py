from __future__ import annotations

from urllib.parse import quote, unquote, urlsplit, urlunsplit

STREAM_SCHEMES = ("rtsp", "rtmp", "http", "https")


def normalize_stream_url(source: str) -> str:
    source_text = source.strip()
    if not source_text:
        return source_text

    parsed = urlsplit(source_text)
    if parsed.scheme.lower() not in STREAM_SCHEMES or "@" not in parsed.netloc:
        return source_text

    userinfo, hostinfo = parsed.netloc.rsplit("@", 1)
    if not userinfo:
        return source_text

    if ":" in userinfo:
        username, password = userinfo.split(":", 1)
        normalized_userinfo = (
            f"{quote(unquote(username), safe='')}:{quote(unquote(password), safe='')}"
        )
    else:
        normalized_userinfo = quote(unquote(userinfo), safe="")

    normalized_netloc = f"{normalized_userinfo}@{hostinfo}"
    return urlunsplit((parsed.scheme, normalized_netloc, parsed.path, parsed.query, parsed.fragment))
