"""Stdio MCP bridge. The running HTTP workbench owns the shared model."""
import os
import base64
import httpx
from mcp.server.fastmcp import FastMCP, Image

mcp = FastMCP('Voxel Studio')
URL = os.environ.get('VOXEL_STUDIO_URL', 'http://127.0.0.1:8765').rstrip('/')


def request(method, path, **kwargs):
    try:
        response = httpx.request(method, URL + path, timeout=60, **kwargs)
        response.raise_for_status()
        return response
    except httpx.ConnectError as e:
        raise ValueError('Start voxel-studio before using agent tools') from e


@mcp.tool()
def get_model() -> dict:
    """Read voxels, size, revision, reference views and comparison scores. x right, y up, z front."""
    state = request('GET', '/api/state').json()
    state.pop('renders')
    state['reference_views'] = list(state.pop('targets'))
    return state


@mcp.tool()
def edit_voxels(edits: list[dict], revision: int) -> dict:
    """Atomic batch of {x,y,z,color:[r,g,b]} edits; color:null erases. Pass current revision."""
    return request('POST', '/api/action', json={'op':'edit','edits':edits,'revision':revision}).json()


@mcp.tool()
def carve_from_references(revision: int) -> dict:
    """Replace geometry with the intersection of reference silhouettes. Undo is available."""
    return request('POST', '/api/action', json={'op':'carve','revision':revision}).json()


@mcp.tool()
def compare_views() -> list:
    """Return scores and a PNG strip: target | render | pink mismatch. Rows follow reference_views order."""
    state = request('GET', '/api/state').json()
    return [str({'row_order':list(state['targets']), 'scores':state['scores'], 'revision':state['revision']}),
            Image(data=request('GET','/api/comparison.png').content, format='png')]


@mcp.tool()
def render_view(view: str) -> Image:
    """Render front, right, back, left, top or bottom as an orthographic PNG."""
    state = request('GET', '/api/state').json()
    if view not in state['renders']: raise ValueError('Unknown camera view')
    return Image(data=base64.b64decode(state['renders'][view].split(',')[1]), format='png')


@mcp.tool()
def get_voxel_slice(axis: str, index: int) -> dict:
    """Read occupied voxels on an x, y or z slice, retaining world coordinates."""
    state = request('GET', '/api/state').json()
    if axis not in ('x','y','z') or not 0 <= index < state['size']: raise ValueError('Invalid slice')
    return {'revision':state['revision'], 'voxels':[v for v in state['voxels'] if v['xyz'.index(axis)] == index]}


@mcp.tool()
def undo(revision: int) -> dict:
    """Undo the most recent shared workbench action."""
    return request('POST', '/api/action', json={'op':'undo','revision':revision}).json()


@mcp.prompt()
def reconstruct() -> str:
    return ('Read get_model, then compare_views. If empty, carve_from_references. '
            'Iteratively use bounded edit_voxels batches with current revision; inspect compare_views after each batch. '
            'Undo regressions. Stop after 20 iterations or when all mismatched_pixels are zero. '
            'Report remaining ambiguity honestly; silhouettes cannot reveal hidden cavities. '
            'Never claim success based on silhouette scores alone when colors still disagree.')


def main(): mcp.run(transport='stdio')
