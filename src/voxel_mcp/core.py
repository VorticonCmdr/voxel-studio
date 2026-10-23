from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

VIEWS = ('front', 'right', 'back', 'left', 'top', 'bottom')


def png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


def data_url(image: Image.Image) -> str:
    return 'data:image/png;base64,' + base64.b64encode(png(image)).decode()


class Model:
    """x right, y up, z toward front. Arrays are indexed [x,y,z,rgba]."""

    def __init__(self, size=16):
        if type(size) is not int or not 2 <= size <= 64:
            raise ValueError('Size must be an integer from 2 to 64')
        self.size = size
        self.grid = np.zeros((size, size, size, 4), dtype=np.uint8)
        self.targets: dict[str, np.ndarray] = {}

    def rays(self, view):
        """Return [image row, image column, nearest-to-farthest, rgba]."""
        g = self.grid
        if view == 'front': return g.transpose(1, 0, 2, 3)[::-1, :, ::-1]
        if view == 'back': return g.transpose(1, 0, 2, 3)[::-1, ::-1, :]
        if view == 'right': return g.transpose(1, 2, 0, 3)[::-1, ::-1, ::-1]
        if view == 'left': return g.transpose(1, 2, 0, 3)[::-1, :, :]
        if view == 'top': return g.transpose(2, 0, 1, 3)[:, :, ::-1]
        if view == 'bottom': return g.transpose(2, 0, 1, 3)[::-1, :, :]
        raise ValueError(f'Unknown view: {view}')

    def render(self, view):
        rays = self.rays(view)
        occupied = rays[..., 3] > 0
        first = occupied.argmax(axis=2)
        rows, cols = np.indices((self.size, self.size))
        result = rays[rows, cols, first].copy()
        result[~occupied.any(axis=2)] = 0
        return result

    def import_views(self, views):
        targets = {}
        for view, source in views.items():
            self.rays(view)
            raw = base64.b64decode(source.split(',')[-1], validate=True)
            if len(raw) > 8_000_000: raise ValueError('Image exceeds 8 MB')
            with Image.open(io.BytesIO(raw)) as im:
                if im.size != (self.size, self.size):
                    raise ValueError(f'{view}: expected {self.size}×{self.size} pixels')
                a = np.array(im.convert('RGBA'))
            a[a[..., 3] < 128] = 0
            a[a[..., 3] >= 128, 3] = 255
            targets[view] = a
        self.targets.update(targets)

    def carve(self):
        if not self.targets: raise ValueError('Import at least one reference view first')
        self.grid[:] = [155, 178, 204, 255]
        for view, target in self.targets.items():
            self.rays(view)[target[..., 3] == 0] = 0
        # Assign surface colors only; later views take precedence at shared corners.
        for view, target in self.targets.items():
            rays = self.rays(view)
            occupied = rays[..., 3] > 0
            rows, cols = np.where(occupied.any(axis=2))
            rays[rows, cols, occupied.argmax(axis=2)[rows, cols]] = target[rows, cols]

    def edit(self, edits):
        if len(edits) > 32768: raise ValueError('At most 32768 edits per batch')
        validated = []
        for e in edits:
            xyz = [e.get(k) for k in ('x', 'y', 'z')]
            if any(type(v) is not int or not 0 <= v < self.size for v in xyz):
                raise ValueError('Voxel coordinates must be integers inside the grid')
            color = e.get('color')
            if color is None: color = [0, 0, 0, 0]
            elif len(color) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in color):
                raise ValueError('Color must be [r,g,b] in 0..255 or null to erase')
            else: color = [*color, 255]
            validated.append((xyz, color))
        for xyz, color in validated: self.grid[tuple(xyz)] = color

    def compare(self):
        scores = {}
        strips = []
        for view, target in self.targets.items():
            actual = self.render(view)
            a, b = actual[..., 3] > 0, target[..., 3] > 0
            union = a | b
            mismatch = np.any(actual != target, axis=2)
            diff = np.zeros_like(actual)
            diff[mismatch] = [255, 77, 120, 255]
            scores[view] = {
                'silhouette_iou': float((a & b).sum() / union.sum()) if union.any() else 1.0,
                'mismatched_pixels': int(mismatch.sum()),
                'rgb_mae': float(np.abs(actual[..., :3].astype(float) - target[..., :3]).sum(axis=2)[union].mean() / 3) if union.any() else 0.0,
            }
            strips.append(np.concatenate((target, actual, diff), axis=1))
        image = Image.fromarray(np.concatenate(strips, axis=0)) if strips else Image.new('RGBA', (3*self.size, self.size))
        return scores, image

    def serialize(self):
        coords = np.argwhere(self.grid[..., 3] > 0)
        return {'version': 1, 'size': self.size,
                'voxels': [[*map(int, p), *map(int, self.grid[tuple(p)][:3])] for p in coords],
                'targets': {v: data_url(Image.fromarray(a)) for v, a in self.targets.items()}}

    @classmethod
    def deserialize(cls, data):
        if data.get('version') != 1: raise ValueError('Unsupported project version')
        model = cls(data['size'])
        voxels = data['voxels']
        if len(voxels) > model.size**3: raise ValueError('Too many voxels')
        if any(len(v) != 6 for v in voxels): raise ValueError('Invalid voxel record')
        # Import in bounded chunks; edit validates before changing the candidate model.
        for start in range(0, len(voxels), 32768):
            model.edit([dict(x=v[0], y=v[1], z=v[2], color=v[3:]) for v in voxels[start:start+32768]])
        model.import_views(data.get('targets', {}))
        return model

    def obj(self):
        # Surface-only quads, with widely supported optional vertex RGB extension.
        faces = [((-1,0,0), ((0,0,0),(0,0,1),(0,1,1),(0,1,0))),
                 ((1,0,0), ((1,0,0),(1,1,0),(1,1,1),(1,0,1))),
                 ((0,-1,0), ((0,0,0),(1,0,0),(1,0,1),(0,0,1))),
                 ((0,1,0), ((0,1,0),(0,1,1),(1,1,1),(1,1,0))),
                 ((0,0,-1), ((0,0,0),(0,1,0),(1,1,0),(1,0,0))),
                 ((0,0,1), ((0,0,1),(1,0,1),(1,1,1),(0,1,1)))]
        lines = ['# Voxel Studio; unit cubes; vertex RGB extension']
        index = 1
        for p in np.argwhere(self.grid[..., 3] > 0):
            color = self.grid[tuple(p)][:3] / 255
            for normal, corners in faces:
                neighbor = p + normal
                if np.all(neighbor >= 0) and np.all(neighbor < self.size) and self.grid[tuple(neighbor)][3]: continue
                for corner in corners:
                    xyz = p + corner
                    lines.append('v ' + ' '.join(map(str, xyz)) + ' ' + ' '.join(f'{c:.5f}' for c in color))
                lines.append('f ' + ' '.join(str(index+i) for i in range(4)))
                index += 4
        return '\n'.join(lines) + '\n'


def demo():
    model = Model(16)
    # A little survey robot, deliberately asymmetric so camera flips are visible.
    for x in range(4,12):
        for y in range(3,13):
            for z in range(5,11):
                model.grid[x,y,z] = [108, 204, 179, 255]
    model.grid[5:11,8:11,10] = [25, 46, 65, 255]
    model.grid[6,9,10] = model.grid[9,9,10] = [255, 215, 119, 255]
    model.grid[3:5,4:8,6:9] = model.grid[11:13,4:8,6:9] = [232,166,98,255]
    model.grid[5:7,1:3,6:10] = model.grid[9:11,1:3,6:10] = [75,100,125,255]
    model.grid[10,13:15,7] = [232,166,98,255]
    model.targets = {v: model.render(v) for v in ('front','right','back','top')}
    model.grid[:] = 0
    model.carve()
    return model
