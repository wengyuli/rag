#!/usr/bin/env python3
"""Import generated, fictional studio assets into the local library.

Reads numbered files only. Existing names are reused only when original bytes
match; never overwrites or removes other assets. Uses the standard library.
"""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request
import uuid


class Client:
    def __init__(self, base):
        self.base = base.rstrip('/')
        self.token = ''
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        form = urllib.parse.urlencode({'username': os.getenv('DEMO_USERNAME', 'admin'),
                                      'password': os.getenv('DEMO_PASSWORD', 'admin123')}).encode()
        self.token = self.json('/api/auth/login', 'POST', form,
                               'application/x-www-form-urlencoded')['access_token']

    def request(self, path, method='GET', data=None, content_type=None):
        headers = {'Authorization': 'Bearer ' + self.token} if self.token else {}
        if content_type:
            headers['Content-Type'] = content_type
        return self.opener.open(urllib.request.Request(self.base + path, data=data,
                                headers=headers, method=method), timeout=600)

    def json(self, path, method='GET', data=None, content_type=None):
        with self.request(path, method, data, content_type) as response:
            return json.load(response)

    def original(self, doc_id):
        with self.request(f'/api/files/assets/{doc_id}') as response:
            if response.headers.get_content_type() == 'application/json':
                return json.load(response)['content'].encode('utf-8')
            return response.read()

    def upload(self, path):
        existing = [item for item in self.json('/api/documents') if item['name'] == path.name and item['isGlobal']]
        if existing:
            if len(existing) != 1 or self.original(existing[0]['id']) != path.read_bytes():
                raise RuntimeError('Existing asset differs; refusing to overwrite: ' + path.name)
            return existing[0]['id']
        boundary = 'studio-demo-' + uuid.uuid4().hex
        data = (f'--{boundary}\r\nContent-Disposition: form-data; name="is_public"\r\n\r\ntrue\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
                'Content-Type: application/octet-stream\r\n\r\n').encode() + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
        return self.json('/api/documents/upload', 'POST', data, f'multipart/form-data; boundary={boundary}')['id']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('runtime/content-demo'))
    parser.add_argument('--base-url', default='http://127.0.0.1:8090')
    args = parser.parse_args()
    paths = sorted(path for path in args.directory.glob('[0-9][0-9]_*')
                   if path.suffix.lower() in {'.txt', '.pdf', '.png', '.mp4'})
    if len(paths) != 4:
        raise RuntimeError('Expected four generated assets; run create_content_demo.py first')
    client = Client(args.base_url)
    records = {client.upload(path): path.name for path in paths}
    pending = set(records)
    states = {}
    deadline = time.monotonic() + 1800
    while pending and time.monotonic() < deadline:
        for doc_id in sorted(pending):
            item = client.json('/api/documents/' + str(doc_id))
            state = (item['status'], item['stage'])
            if states.get(doc_id) != state:
                print(records[doc_id], item['status'], item['stage'], flush=True)
                states[doc_id] = state
            if item['status'] == 'indexed':
                pending.remove(doc_id)
            elif item['status'] == 'failed':
                raise RuntimeError(records[doc_id] + ': ' + str(item['error']))
        if pending:
            time.sleep(3)
    if pending:
        raise TimeoutError('Some demo assets are still processing')
    (args.directory / 'import-result.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    print('All four studio assets are ready for questions.', flush=True)


if __name__ == '__main__':
    main()
