#!/usr/bin/env python3
"""Ask four business questions against the imported fictional studio assets."""
import argparse
import json
from pathlib import Path
import time
from load_demo import Client


def ask(client, question):
    payload=json.dumps({'messages':[{'role':'user','content':question}], 'stream':True}).encode()
    result={'question':question,'answer':'','sources':[]}
    with client.request('/api/chat','POST',payload,'application/json') as response:
        for line in response:
            if not line.strip():continue
            event=json.loads(line)
            if event['type']=='content':result['answer']+=event['data']
            elif event['type']=='sources':result['sources']=event['data']
            elif event['type']=='session_id':result['session_id']=event['data']
            elif event['type']=='error':raise RuntimeError('Question returned an error')
    if not result['answer'] or not result['sources']:raise AssertionError('Missing answer or sources')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8090')
    args=parser.parse_args()
    client=Client(args.base_url)
    scenarios=[
        ('城市漫游栏目由谁负责，每周什么时候发布？发布前由谁审核？','document',['林晓','陈晨']),
        ('城市漫游封面规范要求的画布尺寸和主色是什么？','document',['1600','1000','315E4B']),
        ('城市漫游封面提案图片的主标题是什么，画面中有哪些主要元素？','image',['周末去散步']),
        ('拍摄流程培训视频中，第一步和第二步分别是什么？','video',['收音','电量','口播']),
    ]
    report={'ok':False,'chats':[]}
    started=time.monotonic()
    try:
        for question,kind,terms in scenarios:
            result=ask(client,question)
            report['chats'].append(result)
            print(question,result['answer'],flush=True)
            assert all(term in result['answer'] for term in terms), 'Expected facts missing'
            assert any(source['media_type']==kind for source in result['sources']), 'Expected asset citation missing'
            if kind=='video':
                assert '15' in result['answer'] or '十五' in result['answer'], 'Expected 15-second introduction'
                assert any(source['source_kind']=='audio' and source['start_seconds'] is not None for source in result['sources']), 'Speech citation missing'
            history=client.json('/api/chat/sessions/'+result['session_id'])
            assert any(message['role']=='assistant' and message['content']==result['answer'] for message in history)
        report['ok']=True
    finally:
        report['seconds']=round(time.monotonic()-started,2)
        Path('runtime/content-demo/qa-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Studio demo verification passed.',flush=True)


if __name__=='__main__':main()
