from __future__ import annotations
import argparse
import copy
import json
import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from .core import Model, demo, data_url, png

STATIC = Path(__file__).parent / 'static'


def create_app(project: Path | None = None):
    app = FastAPI(title='Voxel Studio')
    lock = threading.RLock()
    model = Model.deserialize(json.loads(project.read_text())) if project and project.exists() else demo()
    history = []
    revision = 0

    def save(candidate):
        if project:
            project.parent.mkdir(parents=True, exist_ok=True)
            temp = project.with_suffix('.tmp')
            temp.write_text(json.dumps(candidate.serialize()))
            os.replace(temp, project)

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        host = request.headers.get('host', '').split(':')[0]
        origin = request.headers.get('origin')
        if host not in ('127.0.0.1', 'localhost', 'testserver'):
            return Response('Local access only', status_code=403)
        if origin and origin != f'{request.url.scheme}://{request.headers.get("host")}':
            return Response('Cross-origin access denied', status_code=403)
        if int(request.headers.get('content-length', 0)) > 16_000_000:
            return Response('Request too large', status_code=413)
        return await call_next(request)

    @app.get('/')
    def index(): return FileResponse(STATIC / 'index.html')

    @app.get('/api/state')
    def state():
        with lock:
            scores, _ = model.compare()
            return {**model.serialize(), 'revision': revision, 'undo_count': len(history), 'scores': scores,
                    'renders': {v: data_url(Image.fromarray(model.render(v))) for v in ('front','right','back','left','top','bottom')}}

    @app.post('/api/action')
    def action(body: dict):
        nonlocal model, revision
        with lock:
            if body.get('revision', revision) != revision: raise HTTPException(409, 'Model changed; refresh and retry')
            candidate = copy.deepcopy(model)
            try:
                op = body.get('op')
                if op == 'undo':
                    if not history: raise ValueError('Nothing to undo')
                    candidate = copy.deepcopy(history[-1])
                elif op == 'new': candidate = Model(body.get('size', 16))
                elif op == 'demo': candidate = demo()
                elif op == 'load': candidate = Model.deserialize(body['project'])
                elif op == 'import': candidate.import_views(body['views'])
                elif op == 'carve': candidate.carve()
                elif op == 'edit': candidate.edit(body['edits'])
                elif op == 'clear_references': candidate.targets = {}
                else: raise ValueError('Unknown operation')
                save(candidate)
            except (ValueError, KeyError, TypeError, IndexError) as e:
                raise HTTPException(400, str(e)) from e
            if op == 'undo': history.pop()
            else:
                history.append(model)
                del history[:-20]
            model = candidate
            revision += 1
            return {'revision': revision, 'voxels': int((model.grid[...,3] > 0).sum())}

    @app.get('/api/comparison.png')
    def comparison():
        with lock: return Response(png(model.compare()[1]), media_type='image/png')

    @app.get('/api/export/{kind}')
    def export(kind: str):
        with lock:
            if kind == 'json': content, media = json.dumps(model.serialize()), 'application/json'
            elif kind == 'obj': content, media = model.obj(), 'text/plain'
            else: raise HTTPException(404, 'Use json or obj')
            return Response(content, media_type=media, headers={'Content-Disposition': f'attachment; filename="voxel-model.{kind}"'})

    app.mount('/static', StaticFiles(directory=STATIC), name='static')
    return app


def main():
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--project', type=Path, default=Path('workspace/project.json'))
    args = parser.parse_args()
    uvicorn.run(create_app(args.project), host='127.0.0.1', port=args.port)
