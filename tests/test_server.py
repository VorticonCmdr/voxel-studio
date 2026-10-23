from fastapi.testclient import TestClient
from voxel_mcp.server import create_app


def test_shared_state_persistence_undo_and_conflict(tmp_path):
    project=tmp_path/'project.json'
    c=TestClient(create_app(project))
    initial=c.get('/api/state').json()
    assert c.post('/api/action',json={'op':'new','size':8,'revision':0}).status_code==200
    assert c.post('/api/action',json={'op':'edit','edits':[],'revision':0}).status_code==409
    assert c.post('/api/action',json={'op':'undo','revision':1}).status_code==200
    assert c.get('/api/state').json()['voxels']==initial['voxels']
    restored=TestClient(create_app(project))
    assert restored.get('/api/state').json()['voxels']==initial['voxels']
    assert c.get('/api/comparison.png').content.startswith(b'\x89PNG')
    assert c.get('/api/export/obj').status_code==200
    assert c.get('/').status_code==200
    assert c.post('/api/action',json={'op':'edit','edits':[{'x':-1}]}).status_code==400
    assert c.get('/api/state').json()['revision']==2


def test_cross_origin_and_host_rejected():
    c=TestClient(create_app())
    assert c.post('/api/action',json={'op':'new'},headers={'Origin':'https://evil.example'}).status_code==403
    assert c.get('/api/state',headers={'Host':'evil.example'}).status_code==403
