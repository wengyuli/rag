"""Upload/queue/retry/failure regressions without production data or model calls.

SQLite stores real ORM rows in a temporary directory. Transaction-scoped Python
locks stand in for PostgreSQL advisory locks for the concurrent upload test;
PostgreSQL-specific advisory and SKIP LOCKED semantics are not tested here.
Run: python -m unittest discover -s tests -p 'test_ingestion_api.py' -v
"""
import concurrent.futures
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.elements import TextClause

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'llamaindex_rag'))
from asset_access import asset_path
from database import Base
from dependencies import get_current_user, get_db, oauth2_scheme
import ingestion
from media_extract import ExtractionResult, MediaChunk, MediaExtractionError
import media_extract
from models import DocumentRecord, User, Workspace
import rag_engine
from routers import documents


@compiles(JSONB, 'sqlite')
def sqlite_jsonb(type_, compiler, **kwargs):
    return 'JSON'


class IsolatedSession(Session):
    locks = {}
    locks_mutex = threading.Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.held_locks = []

    def execute(self, statement, params=None, *args, **kwargs):
        if isinstance(statement, TextClause) and str(statement).startswith('SELECT pg_advisory_xact_lock'):
            with self.locks_mutex:
                lock = self.locks.setdefault(params['key'], threading.Lock())
            lock.acquire()
            self.held_locks.append(lock)
            return None
        return super().execute(statement, params, *args, **kwargs)

    def release_locks(self):
        while self.held_locks:
            self.held_locks.pop().release()

    def commit(self):
        try:
            return super().commit()
        finally:
            self.release_locks()

    def rollback(self):
        try:
            return super().rollback()
        finally:
            self.release_locks()

    def close(self):
        try:
            return super().close()
        finally:
            self.release_locks()


class IngestionAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rag-ingestion-test-')
        self.root = Path(self.temporary.name)
        self.files = self.root / 'files'
        self.files.mkdir()
        self.environment = patch.dict(os.environ, {'FILES_ROOT': str(self.files)})
        self.environment.start()
        self.engine = create_engine('sqlite:///' + str(self.root / 'test.sqlite'),
                                    connect_args={'check_same_thread': False, 'timeout': 15})
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, class_=IsolatedSession)
        with self.factory() as db:
            db.add_all([Workspace(id='global', name='Public'), Workspace(id='a', name='A'),
                        Workspace(id='b', name='B')])
            db.flush()
            db.add_all([
                User(id=1, username='admin', email='admin@test.invalid', role='admin', department_id='global'),
                User(id=2, username='member', email='member@test.invalid', role='member', department_id='a'),
                User(id=3, username='other', email='other@test.invalid', role='member', department_id='b'),
                User(id=4, username='unassigned', email='none@test.invalid', role='member', department_id=None),
            ])
            db.commit()
        self.app = FastAPI()
        self.app.include_router(documents.router)
        def session_dependency():
            with self.factory() as db:
                yield db
        def identity(token=Depends(oauth2_scheme), db=Depends(get_db)):
            user = db.query(User).filter_by(username=token).first()
            if user is None:
                raise HTTPException(401)
            return user
        self.app.dependency_overrides[get_db] = session_dependency
        self.app.dependency_overrides[get_current_user] = identity
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.sessions_patch = patch.object(ingestion, 'SessionLocal', self.factory)
        self.sessions_patch.start()
        ingestion._stop.clear()
        self.index = MagicMock()
        self.index_patch = patch.object(rag_engine, 'get_vector_index', return_value=self.index)
        self.index_patch.start()

    def tearDown(self):
        ingestion._stop.clear()
        self.index_patch.stop()
        self.sessions_patch.stop()
        self.client.__exit__(None, None, None)
        self.engine.dispose()
        self.environment.stop()
        self.temporary.cleanup()

    def auth(self, username='member'):
        return {'Authorization': 'Bearer ' + username}

    def upload(self, name='test.txt', data=b'Private fixture with enough text.', user='member', public=False):
        return self.client.post('/api/documents/upload', headers=self.auth(user),
                                files={'file': (name, data, 'application/octet-stream')},
                                data={'is_public': str(public).lower()})

    def record(self, doc_id):
        with self.factory() as db:
            doc = db.get(DocumentRecord, int(doc_id))
            db.expunge(doc)
            return doc

    def state(self, doc_id, state, **kwargs):
        with self.factory() as db:
            db.query(DocumentRecord).filter_by(id=int(doc_id)).update({
                'processing_status': state, **kwargs})
            db.commit()

    def test_upload_is_accepted_before_any_model_call_and_preserves_original(self):
        response = self.upload(data=b'Original fixture contents.')
        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body['status'], 'queued')
        row = self.record(body['id'])
        self.assertEqual(row.processing_progress, 0)
        self.assertEqual(row.workspace_id, 'a')
        self.assertEqual(row.media_type, 'document')
        self.assertTrue(row.storage_filename.startswith('_assets/'))
        self.assertEqual(asset_path(row).read_bytes(), b'Original fixture contents.')
        self.index.insert_nodes.assert_not_called()
        details = self.client.get('/api/documents/' + body['id'], headers=self.auth()).json()
        self.assertEqual((details['status'], details['progress']), ('queued', 0))

    def test_duplicate_upload_never_overwrites_existing_data(self):
        first = self.upload(data=b'Original contents remain unchanged.').json()
        self.state(first['id'], 'indexed', processing_progress=100)
        second = self.upload(data=b'Unexpected replacement data.')
        self.assertEqual(second.status_code, 409)
        self.assertEqual(asset_path(self.record(first['id'])).read_bytes(), b'Original contents remain unchanged.')
        with self.factory() as db:
            self.assertEqual(db.query(DocumentRecord).count(), 1)
        self.index.delete_ref_doc.assert_not_called()

    def test_concurrent_same_name_uploads_return_one_202_and_one_409(self):
        payload = b'concurrent upload fixture ' * 60000
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.upload, 'parallel.txt', payload) for _ in range(2)]
            responses = [future.result(timeout=15) for future in futures]
        self.assertEqual(sorted(r.status_code for r in responses), [202, 409])
        with self.factory() as db:
            rows = db.query(DocumentRecord).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(asset_path(rows[0]).read_bytes(), payload)

    def test_invalid_empty_and_oversized_uploads_leave_no_files_or_rows(self):
        for name, data, code in (('../escape.txt', b'bad', 400), ('empty.txt', b'', 400),
                                 ('program.exe', b'bad', 415)):
            self.assertEqual(self.upload(name, data).status_code, code)
        with patch.object(documents, 'MAX_UPLOAD_BYTES', 4):
            self.assertEqual(self.upload('large.txt', b'12345').status_code, 413)
        self.assertEqual(list(self.files.rglob('original*')), [])
        with self.factory() as db:
            self.assertEqual(db.query(DocumentRecord).count(), 0)

    def test_public_upload_requires_admin_and_list_ignores_foreign_workspace_hint(self):
        self.assertEqual(self.upload(public=True).status_code, 403)
        self.assertEqual(self.upload(user='unassigned').status_code, 400)
        own = self.upload('own.txt').json()['id']
        hidden = self.upload('hidden.txt', user='other').json()['id']
        public = self.upload('public.txt', user='admin', public=True).json()['id']
        visible = self.client.get('/api/documents?workspace_id=b', headers=self.auth()).json()
        self.assertEqual({d['id'] for d in visible}, {own, public})
        self.assertEqual(self.client.get('/api/documents/' + hidden, headers=self.auth()).status_code, 404)

    def test_post_commit_refresh_failure_does_not_remove_queued_file(self):
        with patch.object(IsolatedSession, 'refresh', side_effect=RuntimeError('post-commit refresh outage')):
            response = self.upload('refresh.txt')
        self.assertEqual(response.status_code, 202, response.text)
        self.assertTrue(asset_path(self.record(response.json()['id'])).is_file())

    def test_uncertain_commit_retains_file_if_record_was_committed(self):
        commit = IsolatedSession.commit
        def ambiguous_commit(db):
            commit(db)
            raise RuntimeError('connection lost after commit reached the database')
        with patch.object(IsolatedSession, 'commit', ambiguous_commit):
            response = self.upload('uncertain.txt')
        self.assertEqual(response.status_code, 500)
        with self.factory() as db:
            row = db.query(DocumentRecord).filter_by(filename='uncertain.txt').one()
            self.assertEqual(row.processing_status, 'queued')
            self.assertTrue(asset_path(row).is_file())
        self.assertEqual(self.upload('uncertain.txt').status_code, 409)

    def test_failed_retry_resets_status_and_conflicts_with_other_states(self):
        doc_id = self.upload().json()['id']
        for state in ('queued', 'processing', 'indexed'):
            self.state(doc_id, state)
            self.assertEqual(self.client.post(f'/api/documents/{doc_id}/retry', headers=self.auth()).status_code, 409)
        self.state(doc_id, 'failed', processing_error='safe test failure', processing_progress=45)
        response = self.client.post(f'/api/documents/{doc_id}/retry', headers=self.auth())
        self.assertEqual(response.status_code, 202)
        row = self.record(doc_id)
        self.assertEqual((row.processing_status, row.processing_progress, row.processing_error), ('queued', 0, None))
        self.assertTrue(asset_path(row).is_file())

    def test_retry_requires_permission_and_an_existing_original(self):
        doc_id = self.upload().json()['id']
        self.state(doc_id, 'failed')
        self.assertEqual(self.client.post(f'/api/documents/{doc_id}/retry', headers=self.auth('other')).status_code, 404)
        asset_path(self.record(doc_id)).unlink()
        self.assertEqual(self.client.post(f'/api/documents/{doc_id}/retry', headers=self.auth()).status_code, 409)
        self.assertEqual(self.record(doc_id).processing_status, 'failed')

    def test_delete_processing_conflicts_then_removes_queue_and_original(self):
        doc_id = self.upload().json()['id']
        path = asset_path(self.record(doc_id))
        self.state(doc_id, 'processing')
        self.assertEqual(self.client.delete(f'/api/documents/{doc_id}', headers=self.auth()).status_code, 409)
        self.assertTrue(path.is_file())
        self.state(doc_id, 'queued')
        self.assertEqual(self.client.delete(f'/api/documents/{doc_id}', headers=self.auth('other')).status_code, 404)
        self.assertEqual(self.client.delete(f'/api/documents/{doc_id}', headers=self.auth()).status_code, 200)
        self.assertFalse(path.exists())
        self.index.delete_ref_doc.assert_called_once_with(f'asset:{doc_id}', delete_from_docstore=True)

    def test_recovery_requeues_only_interrupted_jobs_and_claims_oldest(self):
        ids = [self.upload(f'{state}.txt').json()['id'] for state in ('processing', 'failed', 'indexed', 'queued')]
        for doc_id, state in zip(ids, ('processing', 'failed', 'indexed', 'queued')):
            self.state(doc_id, state, processing_progress=50, processing_error='old failure')
        ingestion._recover_interrupted()
        self.assertEqual([self.record(i).processing_status for i in ids], ['queued', 'failed', 'indexed', 'queued'])
        self.assertEqual(self.record(ids[0]).processing_progress, 0)
        self.assertIsNone(self.record(ids[0]).processing_error)
        self.assertEqual(ingestion._claim_next(), int(ids[0]))
        self.assertEqual(ingestion._claim_next(), int(ids[3]))
        self.assertIsNone(ingestion._claim_next())

    def test_worker_indexes_then_marks_ready_and_includes_asset_metadata(self):
        doc_id = self.upload().json()['id']
        self.state(doc_id, 'processing')
        ingestion.process_asset(int(doc_id))
        row = self.record(doc_id)
        self.assertEqual((row.processing_status, row.processing_progress), ('indexed', 100))
        nodes = self.index.insert_nodes.call_args.args[0]
        self.assertTrue(nodes)
        self.assertTrue(all(n.metadata['document_id'] == int(doc_id) for n in nodes))
        self.assertTrue(all(n.ref_doc_id == f'asset:{doc_id}' for n in nodes))
        self.assertEqual(row.media_metadata['chunk_count'], len(nodes))

    def test_worker_preprocessing_path_failure_is_failed_not_forever_processing(self):
        doc_id = self.upload().json()['id']
        self.state(doc_id, 'processing', storage_filename='../private.txt')
        with self.assertLogs(ingestion.logger, level='ERROR'):
            ingestion.process_asset(int(doc_id))
        row = self.record(doc_id)
        self.assertEqual(row.processing_status, 'failed')
        self.assertNotIn('private.txt', row.processing_error)
        self.index.insert_nodes.assert_not_called()

    def test_partial_index_failure_cleans_vectors_and_hides_internal_error(self):
        doc_id = self.upload().json()['id']
        self.state(doc_id, 'processing')
        self.index.insert_nodes.side_effect = ValueError('secret content /private/file and internal connection string')
        with self.assertLogs(ingestion.logger, level='ERROR'):
            ingestion.process_asset(int(doc_id))
        row = self.record(doc_id)
        self.assertEqual(row.processing_status, 'failed')
        self.assertNotIn('secret', row.processing_error)
        self.assertEqual(self.index.delete_ref_doc.call_count, 2)
        self.assertTrue(asset_path(row).is_file())

    def test_lost_worker_ownership_prevents_indexing_and_leaves_recoverable_state(self):
        doc_id = self.upload().json()['id']
        self.state(doc_id, 'processing')
        def ownership_lost():
            raise InterruptedError('ownership lost')
        ingestion.process_asset(int(doc_id), ownership_lost)
        self.assertEqual(self.record(doc_id).processing_status, 'processing')
        self.index.insert_nodes.assert_not_called()
        self.index.delete_ref_doc.assert_not_called()

    def test_scanned_pdf_passes_png_filename_and_keeps_page_location(self):
        import fitz
        source = self.root / 'scan.pdf'
        with fitz.open() as pdf:
            pdf.new_page(width=180, height=180)
            pdf.save(source)
        def read_scan(path, filename, artifacts, progress):
            self.assertEqual(Path(filename).suffix, '.png')
            self.assertIn('第 1 页', filename)
            self.assertTrue(path.is_file())
            return ExtractionResult([MediaChunk('测试扫描页上写着蓝鲸项目负责人为林晓。')], {})
        with patch.object(media_extract, 'extract_media', side_effect=read_scan):
            result = ingestion.extract_document(source, 'scan.pdf', self.root / 'artifacts', lambda *_: None)
        self.assertEqual(result.metadata['ocr_pages'], 1)
        self.assertEqual(result.chunks[0].metadata['page'], 1)
        self.assertTrue(any('核对原文' in warning for warning in result.metadata['warnings']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
