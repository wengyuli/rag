"""Media serving and citation tests using real ASGI responses, no database/model server.

Run: python -m unittest discover -s tests -p 'test_media_routes.py' -v
"""
import unittest
from unittest.mock import patch
import os
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'llamaindex_rag'))

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from dependencies import get_current_user, get_db, oauth2_scheme
from routers import files, chat
from llama_index.core.schema import NodeWithScore, TextNode

class Query:
    def __init__(self, records):
        self.records = list(records)
    def filter(self, *clauses):
        for clause in clauses:
            key, value = clause.left.name, clause.right.value
            self.records = [d for d in self.records if getattr(d, key) == value]
        return self
    def populate_existing(self):
        return self
    def first(self):
        return self.records[0] if self.records else None

class DB:
    def __init__(self, documents):
        self.documents = documents
    def query(self, model):
        return Query(self.documents)

member = SimpleNamespace(role='member', department_id='a')
other = SimpleNamespace(role='member', department_id='b')
admin = SimpleNamespace(role='admin', department_id=None)

def doc(i, filename, ws='a', kind='document', status='indexed', storage=None):
    return SimpleNamespace(id=i, filename=filename, workspace_id=ws, is_global=ws == 'global',
                           media_type=kind, processing_status=status, storage_filename=storage)

def identity(token=Depends(oauth2_scheme)):
    users = {'member': member, 'other': other, 'admin': admin}
    if token not in users:
        raise HTTPException(401)
    return users[token]

class MediaRouteTests(unittest.TestCase):
    def test_asset_access_ranges_and_location_citations(self):
        with tempfile.TemporaryDirectory(prefix='rag-files-test-') as temp, patch.dict(os.environ, {'FILES_ROOT': temp}):
            root = Path(temp)
            video = root / '_assets/video/original.mp4'
            video.parent.mkdir(parents=True)
            video.write_bytes(b'0123456789abcdefghij')
            thumb = video.parent / 'artifacts/thumbnail.jpg'
            thumb.parent.mkdir()
            thumb.write_bytes(b'\xff\xd8\xfftestjpeg')
            text = root / 'a/legacy.txt'
            text.parent.mkdir()
            text.write_text('本地文档文本', encoding='utf-8')
            image = root / '_assets/image/original.png'
            image.parent.mkdir(parents=True)
            image.write_bytes(b'\x89PNG\r\n\x1a\n')
            documents = [
                doc(1, 'demo.mp4', kind='video', storage='_assets/video/original.mp4'),
                doc(2, 'legacy.txt'),
                doc(3, 'image.png', ws='global', kind='image', storage='_assets/image/original.png'),
                doc(4, 'other.txt', ws='b'),
                doc(5, 'queued.mp4', kind='video', status='queued'),
                doc(6, 'escape.txt', storage='../escape.txt'),
            ]
            db = DB(documents)
            app = FastAPI()
            app.include_router(files.router)
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[get_current_user] = identity
            client = TestClient(app)
            auth = {'Authorization': 'Bearer member'}
            assert client.get('/api/files/assets/1').status_code == 401
            assert client.get('/api/files/assets/1?token=member').status_code == 401
            assert client.get('/api/files/assets/1', headers={'Authorization': 'Bearer other'}).status_code == 404
            assert client.get('/api/files/assets/999', headers=auth).status_code == 404
            response = client.get('/api/files/assets/1', headers={**auth, 'Range': 'bytes=2-5'})
            assert response.status_code == 206, (response.status_code, response.text)
            assert response.content == b'2345'
            assert response.headers['content-range'] == 'bytes 2-5/20'
            assert response.headers['content-type'] == 'video/mp4'
            assert response.headers['content-disposition'].startswith('inline;')
            suffix = client.get('/api/files/assets/1', headers={**auth, 'Range': 'bytes=-4'})
            assert suffix.status_code == 206 and suffix.content == b'ghij'
            assert client.get('/api/files/assets/1', headers={**auth, 'Range': 'bytes=100-'}).status_code == 416
            assert client.get('/api/files/assets/1/thumbnail', headers=auth).content == thumb.read_bytes()
            assert client.get('/api/files/assets/1/thumbnail', headers={'Authorization': 'Bearer other'}).status_code == 404
            assert client.get('/api/files/assets/3/thumbnail', headers=auth).status_code == 404
            assert client.get('/api/files/assets/3', headers=auth).headers['content-type'] == 'image/png'
            assert client.get('/api/files/assets/2', headers=auth).json() == {'type': 'text', 'content': '本地文档文本'}
            assert client.get('/api/files/legacy.txt?doc_workspace_id=a', headers=auth).json()['type'] == 'text'
            assert client.get('/api/files/legacy.txt?doc_workspace_id=a', headers={'Authorization': 'Bearer other'}).status_code == 404
            assert client.get('/api/files/assets/6', headers=auth).status_code == 400
            thumb.unlink()
            thumb.symlink_to(text)
            assert client.get('/api/files/assets/1/thumbnail', headers=auth).status_code == 404

            def node(metadata):
                return NodeWithScore(node=TextNode(text='片段', metadata=metadata), score=0.8)
            candidate_nodes = [node({'document_id': i}) for i in (1, 3, 4, 5, 999)]
            candidate_nodes += [node({'file_name': 'legacy.txt', 'workspace_id': 'a'})]
            allowed = chat.AccessibleAssetNodes(db, member).postprocess_nodes(candidate_nodes)
            assert len(allowed) == 3
            assert [n.metadata.get('document_id') for n in allowed] == [1, 3, None]
            assert len(chat.AccessibleAssetNodes(db, admin).postprocess_nodes(candidate_nodes)) == 4
            records = [
                {'document_id': 1, 'source_kind': 'video_frame', 'start_seconds': 0, 'end_seconds': 0, 'text_chunk': 'frame zero'},
                {'document_id': 1, 'source_kind': 'video_frame', 'start_seconds': 0, 'text_chunk': 'duplicate'},
                {'document_id': 1, 'source_kind': 'video_frame', 'start_seconds': 12, 'text_chunk': 'frame twelve'},
                {'document_id': 1, 'source_kind': 'transcript', 'start_seconds': 12, 'end_seconds': 18, 'text_chunk': 'voice'},
                {'file_name': 'legacy.txt', 'workspace_id': 'a', 'page': 1, 'text_chunk': 'page one'},
                {'file_name': 'legacy.txt', 'workspace_id': 'a', 'page': 2, 'text_chunk': 'page two'},
                {'document_id': 4, 'text_chunk': 'forbidden'},
                {'document_id': 5, 'text_chunk': 'queued'},
                {'document_id': 999, 'text_chunk': 'deleted'},
            ]
            citations = chat._authorized_citations(records, db, member)
            assert len(citations) == 5, citations
            assert citations[0]['start_seconds'] == 0
            assert citations[2]['end_seconds'] == 18
            assert citations[3]['page'] == 1 and citations[4]['page'] == 2
            expected = {'file_name', 'workspace_id', 'document_id', 'media_type', 'source_kind',
                        'start_seconds', 'end_seconds', 'page', 'score', 'text_chunk'}
            assert all(set(s) == expected for s in citations)
            assert records[4].get('document_id') is None  # Historical input was not mutated.
            try:
                chat.ChatRequest(messages=[])
                raise AssertionError('Empty questions were accepted')
            except ValueError:
                pass
            # All assertions run without contacting an external service.


if __name__ == "__main__":
    unittest.main(verbosity=2)
