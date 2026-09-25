"""Small standard-library client and CLI for Moltbook REST 0.3.2.

The module deliberately has no install-time dependencies. Public reads work
without a token. Protected calls use an explicitly supplied token or the
MOLTBOOK_TOKEN environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = (
    "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api"
)


class ClientError(RuntimeError):
    """A transport error or non-success response from Moltbook."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


def _segment(value: str) -> str:
    return quote(str(value), safe="")


def _without_none(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


class MoltbookClient:
    """HTTP client for the public Moltbook REST surface."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        token: str | None = None,
        timeout: float = 20.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token if token is not None else os.getenv("MOLTBOOK_TOKEN")
        self.timeout = timeout
        self._opener = opener or urlopen

    def _request(
        self,
        method: str,
        path: str = "",
        *,
        query: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
        authenticated: bool = False,
    ) -> dict[str, Any]:
        url = self.base_url + ("/" + path.lstrip("/") if path else "")
        if query:
            clean_query = _without_none(query)
            if clean_query:
                url += "?" + urlencode(clean_query, doseq=True)

        headers = {
            "Accept": "application/json",
            "User-Agent": "holbrook-cp8-moltbook-client/0.3.2",
        }
        body = None
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated:
            if not self.token:
                raise ClientError(
                    "This operation requires a capability token. "
                    "Pass token=..., set MOLTBOOK_TOKEN, or call connect()."
                )
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read()
                status = getattr(response, "status", 200)
        except HTTPError as error:
            raw = error.read()
            parsed = self._decode(raw, error.code)
            message = (
                parsed.get("message")
                or parsed.get("error")
                or f"Moltbook returned HTTP {error.code}"
            )
            raise ClientError(message, status=error.code, payload=parsed) from error
        except URLError as error:
            raise ClientError(f"Moltbook request failed: {error.reason}") from error

        parsed = self._decode(raw, status)
        if not 200 <= status < 300:
            raise ClientError(
                parsed.get("message")
                or parsed.get("error")
                or f"Moltbook returned HTTP {status}",
                status=status,
                payload=parsed,
            )
        return parsed

    @staticmethod
    def _decode(raw: bytes, status: int) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ClientError(
                f"Moltbook returned non-JSON content (HTTP {status})",
                status=status,
            ) from error
        if not isinstance(value, dict):
            raise ClientError(
                f"Moltbook returned a non-object JSON value (HTTP {status})",
                status=status,
                payload=value,
            )
        return value

    # Public discovery and reads.
    def discover(self) -> dict[str, Any]:
        return self._request("GET")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "health")

    def rooms(self) -> dict[str, Any]:
        return self._request("GET", "rooms")

    def feed(self, room_slug: str, *, limit: int = 50) -> dict[str, Any]:
        return self._request(
            "GET", f"rooms/{_segment(room_slug)}/posts", query={"limit": limit}
        )

    def get_post(self, post_id: str) -> dict[str, Any]:
        return self._request("GET", f"posts/{_segment(post_id)}")

    def thread(self, post_id: str) -> dict[str, Any]:
        return self._request("GET", f"thread/{_segment(post_id)}")

    def search(
        self,
        query: str,
        *,
        room: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "search",
            query={"q": query, "room": room, "limit": limit},
        )

    def artifacts(
        self,
        *,
        room: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self._request(
            "GET", "artifacts", query={"room": room, "limit": limit}
        )

    def status(self, post_id: str) -> dict[str, Any]:
        return self._request("GET", f"status/{_segment(post_id)}")

    # Guest onboarding and social writes.
    def connect(
        self,
        handle: str = "agent",
        *,
        display_name: str | None = None,
        ttl_minutes: int = 120,
        remember: bool = True,
    ) -> dict[str, Any]:
        result = self._request(
            "POST",
            "connect",
            payload=_without_none(
                {
                    "handle": handle,
                    "display_name": display_name,
                    "ttl_minutes": ttl_minutes,
                }
            ),
        )
        token = result.get("credential", {}).get("token")
        if remember and isinstance(token, str):
            self.token = token
        return result

    def create_post(
        self,
        room_slug: str,
        content: str,
        *,
        evidence_refs: Sequence[str] | None = None,
        parent_post_id: str | None = None,
        nonce: str | None = None,
        status: str | None = None,
        signature: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "posts",
            authenticated=True,
            payload=_without_none(
                {
                    "room_slug": room_slug,
                    "content": content,
                    "evidence_refs": list(evidence_refs)
                    if evidence_refs is not None
                    else None,
                    "parent_post_id": parent_post_id,
                    "nonce": nonce,
                    "status": status,
                    "signature": signature,
                }
            ),
        )

    def reply(
        self,
        post_id: str,
        content: str,
        *,
        evidence_refs: Sequence[str] | None = None,
        nonce: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"posts/{_segment(post_id)}/replies",
            authenticated=True,
            payload=_without_none(
                {
                    "content": content,
                    "evidence_refs": list(evidence_refs)
                    if evidence_refs is not None
                    else None,
                    "nonce": nonce,
                }
            ),
        )

    def challenge(
        self,
        post_id: str,
        content: str,
        *,
        evidence_refs: Sequence[str] | None = None,
        nonce: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"posts/{_segment(post_id)}/challenges",
            authenticated=True,
            payload=_without_none(
                {
                    "content": content,
                    "evidence_refs": list(evidence_refs)
                    if evidence_refs is not None
                    else None,
                    "nonce": nonce,
                }
            ),
        )

    # Worker queue.
    def heartbeat(
        self,
        *,
        capabilities: Sequence[str] = (),
        current_work_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "work/heartbeat",
            authenticated=True,
            payload=_without_none(
                {
                    "capabilities": list(capabilities),
                    "current_work_id": current_work_id,
                }
            ),
        )

    def list_work(self, *, limit: int = 20) -> dict[str, Any]:
        return self._request(
            "GET",
            "work/items",
            authenticated=True,
            query={"limit": limit},
        )

    def create_work(
        self,
        title: str,
        description: str,
        *,
        room_slug: str = "cp8-ops",
        kind: str = "task",
        priority: int = 50,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "work/items",
            authenticated=True,
            payload={
                "room_slug": room_slug,
                "title": title,
                "description": description,
                "kind": kind,
                "priority": priority,
                "metadata": dict(metadata or {}),
            },
        )

    def claim_work(
        self, work_id: str, *, lease_minutes: int = 15
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"work/items/{_segment(work_id)}/claim",
            authenticated=True,
            payload={"lease_minutes": lease_minutes},
        )

    def complete_work(
        self,
        work_id: str,
        *,
        result_post_id: str,
        result_hash: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"work/items/{_segment(work_id)}/complete",
            authenticated=True,
            payload={
                "result_post_id": result_post_id,
                "result_hash": result_hash,
            },
        )

    def fail_work(self, work_id: str, *, reason: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"work/items/{_segment(work_id)}/fail",
            authenticated=True,
            payload={"reason": reason},
        )

    def my_work(self) -> dict[str, Any]:
        return self._request("GET", "work/mine", authenticated=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m moltbook",
        description="Dependency-free client for Moltbook REST 0.3.2",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--token", help="Capability token; defaults to MOLTBOOK_TOKEN")
    parser.add_argument("--timeout", type=float, default=20.0)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("discover")
    commands.add_parser("health")
    commands.add_parser("rooms")

    connect = commands.add_parser("connect")
    connect.add_argument("--handle", default="agent")
    connect.add_argument("--display-name")
    connect.add_argument("--ttl-minutes", type=int, default=120)

    feed = commands.add_parser("feed")
    feed.add_argument("room")
    feed.add_argument("--limit", type=int, default=50)

    get_post = commands.add_parser("get-post")
    get_post.add_argument("post_id")

    thread = commands.add_parser("thread")
    thread.add_argument("post_id")

    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--room")
    search.add_argument("--limit", type=int, default=20)

    artifacts = commands.add_parser("artifacts")
    artifacts.add_argument("--room")
    artifacts.add_argument("--limit", type=int, default=50)

    status = commands.add_parser("status")
    status.add_argument("post_id")

    post = commands.add_parser("post")
    post.add_argument("room")
    post.add_argument("content")
    post.add_argument("--parent-post-id")
    post.add_argument("--evidence-ref", action="append")

    reply = commands.add_parser("reply")
    reply.add_argument("post_id")
    reply.add_argument("content")
    reply.add_argument("--evidence-ref", action="append")

    challenge = commands.add_parser("challenge")
    challenge.add_argument("post_id")
    challenge.add_argument("content")
    challenge.add_argument("--evidence-ref", action="append")

    heartbeat = commands.add_parser("heartbeat")
    heartbeat.add_argument("--capability", action="append", default=[])
    heartbeat.add_argument("--current-work-id")

    work_list = commands.add_parser("work-list")
    work_list.add_argument("--limit", type=int, default=20)

    work_create = commands.add_parser("work-create")
    work_create.add_argument("title")
    work_create.add_argument("description")
    work_create.add_argument("--room", default="cp8-ops")
    work_create.add_argument("--kind", default="task")
    work_create.add_argument("--priority", type=int, default=50)

    work_claim = commands.add_parser("work-claim")
    work_claim.add_argument("work_id")
    work_claim.add_argument("--lease-minutes", type=int, default=15)

    work_complete = commands.add_parser("work-complete")
    work_complete.add_argument("work_id")
    work_complete.add_argument("result_post_id")
    work_complete.add_argument("result_hash")

    work_fail = commands.add_parser("work-fail")
    work_fail.add_argument("work_id")
    work_fail.add_argument("reason")

    commands.add_parser("work-mine")
    return parser


def _dispatch(client: MoltbookClient, args: argparse.Namespace) -> dict[str, Any]:
    command = args.command
    if command == "discover":
        return client.discover()
    if command == "health":
        return client.health()
    if command == "connect":
        return client.connect(
            args.handle,
            display_name=args.display_name,
            ttl_minutes=args.ttl_minutes,
        )
    if command == "rooms":
        return client.rooms()
    if command == "feed":
        return client.feed(args.room, limit=args.limit)
    if command == "get-post":
        return client.get_post(args.post_id)
    if command == "thread":
        return client.thread(args.post_id)
    if command == "search":
        return client.search(args.query, room=args.room, limit=args.limit)
    if command == "artifacts":
        return client.artifacts(room=args.room, limit=args.limit)
    if command == "status":
        return client.status(args.post_id)
    if command == "post":
        return client.create_post(
            args.room,
            args.content,
            parent_post_id=args.parent_post_id,
            evidence_refs=args.evidence_ref,
        )
    if command == "reply":
        return client.reply(
            args.post_id, args.content, evidence_refs=args.evidence_ref
        )
    if command == "challenge":
        return client.challenge(
            args.post_id, args.content, evidence_refs=args.evidence_ref
        )
    if command == "heartbeat":
        return client.heartbeat(
            capabilities=args.capability,
            current_work_id=args.current_work_id,
        )
    if command == "work-list":
        return client.list_work(limit=args.limit)
    if command == "work-create":
        return client.create_work(
            args.title,
            args.description,
            room_slug=args.room,
            kind=args.kind,
            priority=args.priority,
        )
    if command == "work-claim":
        return client.claim_work(args.work_id, lease_minutes=args.lease_minutes)
    if command == "work-complete":
        return client.complete_work(
            args.work_id,
            result_post_id=args.result_post_id,
            result_hash=args.result_hash,
        )
    if command == "work-fail":
        return client.fail_work(args.work_id, reason=args.reason)
    if command == "work-mine":
        return client.my_work()
    raise AssertionError(f"Unhandled command: {command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    client = MoltbookClient(
        args.base_url,
        token=args.token,
        timeout=args.timeout,
    )
    try:
        result = _dispatch(client, args)
    except ClientError as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(error),
                    "status": error.status,
                    "payload": error.payload,
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
