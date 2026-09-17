"""Real-model integration smoke test for generated, fictional media fixtures.

Run create_media_fixtures.py in the backend container first. This script runs
on the host with standard Python and leaves the three public examples visible.
Set SMOKE_BASE_URL, SMOKE_USERNAME, SMOKE_PASSWORD and MEDIA_TIMEOUT as needed.
"""
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
TIMEOUT = float(os.environ.get("MEDIA_TIMEOUT", "1800"))
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOKEN = ""


def request(path, method="GET", data=None, content_type=None, headers=None):
    values = {"Authorization": "Bearer " + TOKEN} if TOKEN else {}
    values.update(headers or {})
    if content_type:
        values["Content-Type"] = content_type
    return OPENER.open(urllib.request.Request(BASE + path, data=data, headers=values, method=method), timeout=600)


def api(path, method="GET", data=None, content_type=None):
    with request(path, method, data, content_type) as response:
        return json.load(response)


def upload(path):
    existing = [item for item in api("/api/documents") if item["name"] == path.name and item["isGlobal"]]
    if existing:
        assert len(existing) == 1
        return existing[0]["id"]
    boundary = "media-smoke-" + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="is_public"\r\n\r\ntrue\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n').encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    with request("/api/documents/upload", "POST", body, f"multipart/form-data; boundary={boundary}") as response:
        assert response.status == 202
        result = json.load(response)
    assert result["status"] == "queued"
    return result["id"]


def wait_indexed(doc_id):
    started = time.monotonic()
    previous = None
    while time.monotonic() - started < TIMEOUT:
        asset = api(f"/api/documents/{doc_id}")
        state = (asset["status"], asset["stage"])
        if state != previous:
            print(asset["name"], asset["status"], asset["stage"], flush=True)
            previous = state
        if asset["status"] == "indexed":
            return asset
        if asset["status"] == "failed":
            raise AssertionError(f"Fixture {asset['name']} failed: {asset['error']}")
        time.sleep(3)
    raise TimeoutError("Media indexing did not finish")


def chat(question):
    data = json.dumps({"messages": [{"role": "user", "content": question}], "stream": True}).encode()
    answer, sources, session_id = "", [], None
    with request("/api/chat", "POST", data, "application/json") as response:
        for line in response:
            if not line.strip():
                continue
            event = json.loads(line)
            if event["type"] == "content":
                answer += event["data"]
            elif event["type"] == "sources":
                sources = event["data"]
            elif event["type"] == "session_id":
                session_id = event["data"]
            elif event["type"] == "error":
                raise AssertionError("Chat returned an error event")
    assert answer and sources and session_id
    history = api("/api/chat/sessions/" + session_id)
    saved = next(message for message in history if message["role"] == "assistant")
    assert saved["content"] == answer and saved["sources"] == sources
    return {"question": question, "answer": answer, "sources": sources, "session_id": session_id}


def main():
    global TOKEN
    started = time.monotonic()
    credentials = urllib.parse.urlencode({"username": os.environ.get("SMOKE_USERNAME", "admin"),
                                          "password": os.environ.get("SMOKE_PASSWORD", "admin123")}).encode()
    TOKEN = api("/api/auth/login", "POST", credentials, "application/x-www-form-urlencoded")["access_token"]
    report = {"ok": False, "assets": [], "chats": []}
    try:
        fixtures = ROOT / "runtime/test-media"
        for name, kind in (("equipment-card.png", "image"), ("training-demo.mp4", "video"), ("scanned-card.pdf", "document")):
            path = fixtures / name
            doc_id = upload(path)
            asset = wait_indexed(doc_id)
            assert asset["media_type"] == kind
            assert asset["metadata"].get("chunk_count", 0) > 0
            with request(f"/api/files/assets/{doc_id}") as response:
                assert response.read() == path.read_bytes(), "Original bytes differ"
            if kind in {"image", "video"}:
                with request(f"/api/files/assets/{doc_id}/thumbnail") as response:
                    assert response.headers.get_content_type() == "image/jpeg" and len(response.read()) > 100
            if kind == "video":
                assert asset["metadata"]["frame_count"] >= 2
                assert asset["metadata"]["speech_chunk_count"] >= 1, "Real speech transcription missing"
                with request(f"/api/files/assets/{doc_id}", headers={"Range": "bytes=0-99"}) as response:
                    assert response.status == 206 and len(response.read()) == 100
            if name == "scanned-card.pdf":
                assert asset["metadata"]["ocr_pages"] >= 1
            report["assets"].append({"id": doc_id, "name": name, "metadata": asset["metadata"]})
        image_answer = chat("equipment-card.png 图片上的设备型号和最大压力分别是多少？")
        assert "ZX-17" in image_answer["answer"] and "0.6" in image_answer["answer"]
        assert any(source["media_type"] == "image" for source in image_answer["sources"])
        report["chats"].append(image_answer)
        video_answer = chat("training-demo.mp4 设备操作培训视频中，语音讲解的第一步和第二步分别是什么？")
        assert any(source["media_type"] == "video" and source["source_kind"] == "audio"
                   and source["start_seconds"] is not None for source in video_answer["sources"])
        assert ("阀" in video_answer["answer"] or "valve" in video_answer["answer"].lower())
        assert ("按钮" in video_answer["answer"] or "button" in video_answer["answer"].lower())
        report["chats"].append(video_answer)
        scanned_answer = chat("scanned-card.pdf 扫描资料里的设备型号和最大压力是多少？")
        assert "ZX-17" in scanned_answer["answer"] and "0.6" in scanned_answer["answer"]
        assert any(source["file_name"] == "scanned-card.pdf" and str(source["page"]) == "1"
                   for source in scanned_answer["sources"])
        report["chats"].append(scanned_answer)
        report["ok"] = True
    finally:
        report["seconds"] = round(time.monotonic() - started, 2)
        (ROOT / "tests/latest-multimodal.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
