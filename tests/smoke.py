#!/usr/bin/env python3
"""Exercise the local RAG API using only Python's standard library.

Overrides: SMOKE_BASE_URL, SMOKE_USERNAME, SMOKE_PASSWORD, SMOKE_TIMEOUT.
Run only after the backend, database, and models are ready. A successful run
leaves one public test document and a new chat session for manual inspection.
"""
import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


TEST_DIR = Path(__file__).resolve().parent
QUESTION = "蓝鲸项目的负责人是谁？标准交付周期是多少个工作日？"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    started = time.perf_counter()
    base_url = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
    username = os.environ.get("SMOKE_USERNAME", "admin")
    password = os.environ.get("SMOKE_PASSWORD", "admin123")
    token = ""
    report = {
        "ok": False,
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "checks": {},
    }
    # Local requests should not go through system HTTP proxies.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def step(name, action):
        step_started = time.perf_counter()
        try:
            value = action()
        except Exception:
            report["checks"][name] = {
                "ok": False, "seconds": round(time.perf_counter() - step_started, 3)
            }
            raise
        report["checks"][name] = {
            "ok": True, "seconds": round(time.perf_counter() - step_started, 3)
        }
        return value

    def request(path, method="GET", data=None, content_type=None):
        headers = {"Accept": "application/json, application/x-ndjson"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
        try:
            return opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            # Never include response bodies or authorization headers in output.
            raise RuntimeError(f"{method} {path} returned HTTP {code}") from None

    def json_request(path, method="GET", data=None, content_type=None):
        with request(path, method, data, content_type) as response:
            return json.load(response)

    def login():
        nonlocal token
        payload = urllib.parse.urlencode({"username": username, "password": password}).encode()
        result = json_request("/api/auth/login", "POST", payload,
                              "application/x-www-form-urlencoded")
        require(isinstance(result, dict) and isinstance(result.get("access_token"), str)
                and result["access_token"], "Login did not return an access token")
        token = result["access_token"]

    def document_list():
        result = json_request("/api/documents?workspace_id=global")
        require(isinstance(result, list), "Document list response is not a list")
        return result

    def upload_or_reuse():
        existing = [item for item in document_list() if item.get("name") == filename]
        if existing:
            public = [item for item in existing if item.get("isGlobal") is True]
            require(len(public) == 1,
                    "Existing test filename is ambiguous or not public; refusing to overwrite")
            report["document_action"] = "reused"
            return
        boundary = "rag-smoke-" + uuid.uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="is_public"\r\n\r\ntrue\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            'Content-Type: text/plain; charset=utf-8\r\n\r\n'
        ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
        result = json_request("/api/documents/upload", "POST", body,
                              f"multipart/form-data; boundary={boundary}")
        require(result.get("status") == "success" and result.get("filename") == filename,
                "Upload did not confirm the expected test filename")
        report["document_action"] = "uploaded"

    def verify_listing():
        matches = [item for item in document_list()
                   if item.get("name") == filename and item.get("isGlobal") is True]
        require(len(matches) == 1, "Expected exactly one public test document")
        require(matches[0].get("status") == "indexed", "Test document is not indexed")

    def verify_file():
        path = "/api/files/" + urllib.parse.quote(filename, safe="") + "?doc_workspace_id=global"
        result = json_request(path)
        require(result.get("type") == "text", "File endpoint did not return text")
        require(result.get("content") == file_bytes.decode("utf-8"),
                "Stored test file differs from the local fixture; refusing to overwrite it")

    def verify_chat():
        payload = json.dumps({"messages": [{"role": "user", "content": QUESTION}],
                              "workspace_id": "global", "stream": True}).encode()
        answer_parts, sources = [], []
        session_id = None
        event_count = 0
        chat_started = time.perf_counter()
        with request("/api/chat", "POST", payload, "application/json") as response:
            require(response.headers.get_content_type() == "application/x-ndjson",
                    "Chat did not return NDJSON")
            for line in response:
                if not line.strip():
                    continue
                event = json.loads(line)
                event_count += 1
                kind = event.get("type")
                if kind == "session_id":
                    session_id = event.get("data")
                elif kind == "sources":
                    require(isinstance(event.get("data"), list), "Sources event is not a list")
                    sources = event["data"]
                elif kind == "content":
                    require(isinstance(event.get("data"), str), "Content event is not text")
                    if not answer_parts:
                        report["first_content_seconds"] = round(time.perf_counter() - chat_started, 3)
                    answer_parts.append(event["data"])
                elif kind == "error":
                    raise RuntimeError("Chat returned an error event")
        answer = "".join(answer_parts)
        report["answer"] = answer
        report["source_filenames"] = sorted({s.get("file_name", "") for s in sources})
        report["ndjson_events"] = event_count
        require(isinstance(session_id, str) and session_id, "Chat omitted its new session ID")
        report["session_id"] = session_id
        require("林晓" in answer, "Answer does not identify 林晓")
        require(re.search(r"(?<!\d)17(?!\d)", answer) is not None,
                "Answer does not contain the expected 17-day value")
        require(any(s.get("file_name") == filename and s.get("workspace_id") == "global"
                    for s in sources), "Chat did not cite the public test document")
        return session_id, answer

    def verify_history(session_id, answer):
        sessions = json_request("/api/chat/sessions")
        require(any(s.get("id") == session_id for s in sessions), "New session is absent from session list")
        messages = json_request("/api/chat/sessions/" + urllib.parse.quote(session_id, safe=""))
        require(any(m.get("role") == "user" and m.get("content") == QUESTION for m in messages),
                "Question was not persisted")
        matches = [m for m in messages if m.get("role") == "assistant" and m.get("content") == answer]
        require(len(matches) == 1, "Streamed answer was not persisted exactly once")
        require(any(s.get("file_name") == filename and s.get("workspace_id") == "global"
                    for s in (matches[0].get("sources") or [])), "Persisted answer lost its file citation")

    try:
        parsed_url = urllib.parse.urlsplit(base_url)
        require(parsed_url.scheme in ("http", "https") and parsed_url.netloc
                and not parsed_url.username and not parsed_url.password
                and not parsed_url.query and not parsed_url.fragment,
                "SMOKE_BASE_URL must be an HTTP(S) URL without credentials, query, or fragment")
        report["base_url"] = base_url
        timeout = float(os.environ.get("SMOKE_TIMEOUT", "600"))
        require(timeout > 0, "SMOKE_TIMEOUT must be positive")
        fixture = TEST_DIR / "local-rag-test.txt"
        filename = fixture.name
        file_bytes = fixture.read_bytes()
        report["filename"] = filename
        step("login", login)
        step("upload_or_reuse", upload_or_reuse)
        step("document_list", verify_listing)
        step("file_download", verify_file)
        session_id, answer = step("chat", verify_chat)
        step("session_history", lambda: verify_history(session_id, answer))
        report["ok"] = True
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        for secret in (token, password):
            if secret:
                error = error.replace(secret, "[REDACTED]")
        report["error"] = error
    report["total_seconds"] = round(time.perf_counter() - started, 3)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    # Also redact secrets if an unexpected server response repeated them in content.
    for secret in (token, password):
        if secret:
            output = output.replace(secret, "[REDACTED]")
    (TEST_DIR / "latest-smoke.json").write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
