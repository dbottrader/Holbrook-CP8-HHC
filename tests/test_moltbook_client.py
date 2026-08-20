import json
import unittest

from moltbook import ClientError, MoltbookClient


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._raw = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class RecordingOpener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return self.responses.pop(0)


class MoltbookClientTests(unittest.TestCase):
    def test_public_feed_encodes_path_and_query(self):
        opener = RecordingOpener(FakeResponse({"posts": []}))
        client = MoltbookClient(
            "https://moltbook.example/api", opener=opener, token=""
        )

        result = client.feed("cp8 ops", limit=7)

        self.assertEqual(result, {"posts": []})
        request, timeout = opener.requests[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(
            request.full_url,
            "https://moltbook.example/api/rooms/cp8%20ops/posts?limit=7",
        )
        self.assertEqual(timeout, 20.0)
        self.assertNotIn("Authorization", request.headers)

    def test_search_omits_absent_room(self):
        opener = RecordingOpener(FakeResponse({"posts": []}))
        client = MoltbookClient("https://moltbook.example", opener=opener, token="")

        client.search("parent hash", limit=3)

        request, _ = opener.requests[0]
        self.assertIn("q=parent+hash", request.full_url)
        self.assertIn("limit=3", request.full_url)
        self.assertNotIn("room=", request.full_url)

    def test_connect_can_remember_returned_token(self):
        token = "hc_" + ("a" * 64)
        opener = RecordingOpener(
            FakeResponse({"ok": True, "credential": {"token": token}}, status=201)
        )
        client = MoltbookClient("https://moltbook.example", opener=opener, token="")

        client.connect("open-agent", display_name="Open Agent", ttl_minutes=60)

        self.assertEqual(client.token, token)
        request, _ = opener.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            json.loads(request.data),
            {
                "handle": "open-agent",
                "display_name": "Open Agent",
                "ttl_minutes": 60,
            },
        )

    def test_reply_uses_dedicated_route_and_bearer_token(self):
        token = "hc_" + ("b" * 64)
        opener = RecordingOpener(FakeResponse({"ok": True, "post": {}}))
        client = MoltbookClient(
            "https://moltbook.example", opener=opener, token=token
        )

        client.reply(
            "parent-id",
            "canonical reply",
            evidence_refs=["sha256:" + ("c" * 64)],
        )

        request, _ = opener.requests[0]
        self.assertEqual(
            request.full_url,
            "https://moltbook.example/posts/parent-id/replies",
        )
        self.assertEqual(request.headers["Authorization"], f"Bearer {token}")
        self.assertEqual(
            json.loads(request.data),
            {
                "content": "canonical reply",
                "evidence_refs": ["sha256:" + ("c" * 64)],
            },
        )

    def test_protected_call_fails_before_network_without_token(self):
        opener = RecordingOpener()
        client = MoltbookClient("https://moltbook.example", opener=opener, token="")

        with self.assertRaisesRegex(ClientError, "requires a capability token"):
            client.heartbeat(capabilities=["read"])

        self.assertEqual(opener.requests, [])

    def test_non_object_json_is_rejected(self):
        opener = RecordingOpener(FakeResponse(b"[]"))
        client = MoltbookClient("https://moltbook.example", opener=opener, token="")

        with self.assertRaisesRegex(ClientError, "non-object JSON"):
            client.health()


if __name__ == "__main__":
    unittest.main()
