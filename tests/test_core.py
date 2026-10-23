import numpy as np
import pytest
from PIL import Image
from voxel_mcp.core import Model, VIEWS, data_url, demo


def test_camera_coordinates_and_occlusion():
    m = Model(4)
    m.edit([dict(x=1,y=2,z=3,color=[255,0,0])])
    expected = {'front':(1,1),'back':(1,2),'right':(1,0),'left':(1,3),'top':(3,1),'bottom':(0,1)}
    for view, (row,col) in expected.items():
        a = m.render(view)
        assert tuple(a[row,col]) == (255,0,0,255)
        assert (a[...,3]>0).sum() == 1
    m.edit([dict(x=1,y=2,z=0,color=[0,0,255])])
    assert tuple(m.render('front')[1,1]) == (255,0,0,255)
    assert tuple(m.render('back')[1,2]) == (0,0,255,255)


def test_carve_preserves_consistent_silhouettes():
    source=Model(8)
    source.grid[1:5,2:7,3:6]=[100,150,200,255]
    source.grid[5:7,2:4,4:6]=[100,150,200,255]
    m=Model(8)
    m.import_views({v:data_url(Image.fromarray(source.render(v))) for v in VIEWS})
    m.carve()
    assert np.array_equal(m.grid[...,3],source.grid[...,3])
    scores,_=m.compare()
    assert all(s['mismatched_pixels']==0 for s in scores.values())


def test_batch_is_atomic():
    m=Model(4)
    with pytest.raises(ValueError): m.edit([dict(x=1,y=1,z=1,color=[1,2,3]),dict(x=99,y=1,z=1,color=[1,2,3])])
    assert not m.grid.any()


def test_project_roundtrip_and_obj():
    m=demo()
    restored=Model.deserialize(m.serialize())
    assert np.array_equal(m.grid,restored.grid)
    for v in m.targets: assert np.array_equal(m.targets[v],restored.targets[v])
    cube=Model(2)
    cube.edit([dict(x=0,y=0,z=0,color=[1,2,3]),dict(x=1,y=0,z=0,color=[1,2,3])])
    assert sum(line.startswith('f ') for line in cube.obj().splitlines())==10


def test_transparent_and_conflicting_views():
    m=Model(4)
    transparent=Image.new('RGBA',(4,4),(255,0,0,0))
    m.import_views({'front':data_url(transparent)})
    m.carve()
    assert not m.grid.any()
    assert m.compare()[0]['front']['silhouette_iou']==1
    m.import_views({'back':data_url(Image.new('RGBA',(4,4),(1,2,3,255)))})
    m.carve()
    assert m.compare()[0]['back']['silhouette_iou']==0


def test_invalid_view_dimensions():
    m=Model(8)
    with pytest.raises(ValueError): m.import_views({'front':data_url(Image.new('RGBA',(4,4)))})
    assert not m.targets
