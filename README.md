# Voxel Studio

A local Python voxel editor and MCP server for reconstructing aligned pixel sprites.
The browser and agent share one model. No model-provider key is needed: your MCP
client provides the agent. This release supplies tools and a refinement prompt;
it does not run an autonomous LLM inside the app.

## Run

```sh
uv sync --group dev
uv run voxel-studio
```

Open http://127.0.0.1:8765. A sample robot loads on first launch. Each change is
saved to `workspace/project.json`; use `--project PATH` for another workspace and
`--port PORT` for another port. Run only one server per project file.

## Try the workflow

1. Orbit the sample robot by dragging; scroll to zoom. Ctrl-click (or ⌘-click)
   a voxel face to select its axis and layer in the slice editor: top/bottom
   selects Y, left/right selects X, and front/back selects Z. Empty-space clicks
   leave the selection unchanged.
2. Choose an axis and layer in the slice editor. Click a cell to paint, erase, or
   pick its color. Projection scores update after each edit.
3. Undo, then try **Reconstruct from silhouettes** to rebuild from the references.
4. For your own sprites, select the matching grid size and **New empty**. Import
   a PNG for each named camera, or select the sheet layout and specify the camera
   names in cell order (left to right, then next row).
5. Click **Reconstruct from silhouettes**. Inspect reference/render/difference
   cards. Pink marks any RGBA mismatch; the shape score measures silhouette IoU.
6. Save JSON to retain voxels and references, or export OBJ surface geometry.

All actions, including New, importing, carving and opening projects, are undoable
(up to 20 actions). Undo history is session-only. OBJ uses the vertex RGB extension;
readers without support will show uncolored geometry. JSON is the lossless format.

## Sprite requirements and coordinate contract

Frames must be square, aligned and exactly the grid size: 2–64 pixels via API,
8/16/32/64 via the UI. Sheet cells have no padding. Use a transparent background;
alpha below 128 is empty, otherwise solid. No resizing or inferred alignment occurs.
All references constrain one object at the same scale and world origin.

World axes: X right, Y up, Z toward the front camera. Pixel row zero is at the top.
Depth always selects the nearest occupied voxel.

| Camera | Pixel column | Pixel row | Near → far |
| --- | --- | --- | --- |
| front | x | N−1−y | z descending |
| back | N−1−x | N−1−y | z ascending |
| right | N−1−z | N−1−y | x descending |
| left | z | N−1−y | x ascending |
| top | x | z | y descending |
| bottom | x | N−1−z | y ascending |

A single view makes an extrusion. Multiple views intersect their silhouettes.
Hidden geometry is ambiguous; inconsistent sprites may carve to an empty volume.
Isometric/perspective drawings need camera calibration and are not supported yet.
Surface colors are initialized in reference insertion order; later views win when
a voxel is visible from multiple directions. Conflicting view colors may be
impossible to reproduce with one opaque color per voxel. Shape agreement alone
is not proof of a correct reconstruction.

## Connect an agent

Keep `voxel-studio` running, then configure a stdio MCP server in your client's
MCP server settings (adapt this generic JSON to the client's configuration format):

```json
{
  "mcpServers": {
    "voxel-studio": {
      "command": "uv",
      "args": ["--directory", "/Users/valentin.pletzer/projects/python/voxel-mcp", "run", "voxel-agent"]
    }
  }
}
```

If using another port, set `VOXEL_STUDIO_URL=http://127.0.0.1:PORT` on the bridge.
The bridge uses the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk),
pinned to its 1.x FastMCP API for this release.

Tools: `get_model`, `edit_voxels`, `carve_from_references`, `compare_views`, `render_view`,
`get_voxel_slice`, `undo`. The `reconstruct` prompt describes a bounded refinement
workflow. `compare_views` returns a real MCP PNG image, not just a file path.

Example agent request:

> Inspect the model and compare the imported views. Improve the geometry and
> colors in small batches, checking comparison images after every batch. Undo
> regressions. Stop after 20 iterations or zero mismatched pixels, and explain
> any remaining ambiguities. Preserve details that already match.

Edits require the last observed revision to prevent stale agent edits overwriting
manual work. Example `edit_voxels` arguments:

```json
{"revision": 0, "edits": [{"x": 4, "y": 8, "z": 10, "color": [108, 204, 179]}]}
```

`color: null` erases. Batch validation is atomic. On a revision conflict, read
`get_model` and reconsider the edit. All bridge operations are visible in the UI
within 2.5 seconds. Use `get_voxel_slice` to avoid reading a large model repeatedly.

## Development

```sh
uv run pytest
```

`core.py` owns projections, carving, metrics and exports; `server.py` owns the
shared model, history and persistence; `agent.py` bridges MCP to that server.
The browser uses a dependency-free Canvas renderer with exposed-face culling.
For dense 64³ volumes its CPU renderer can be slow; smaller sprite grids are the
intended starting point. The server binds to localhost and rejects foreign Host
and Origin headers. It is a single-user development tool, not a hosted service.

See [PLAN.md](PLAN.md) for scope and next steps.

Example PNGs are in `examples/`. Import `robot-sheet.png` at grid size 16 with
cell order `front,right,back,top` to exercise sheet ingestion.

Verified: eight automated core/API tests; a live stdio MCP handshake, comparison
image, render, batch edit and undo; browser slice painting and undo. Run the live
MCP check with `uv run python tests/mcp_smoke.py` while the studio is running.
It temporarily recolors one voxel and restores it through undo; avoid editing
the model concurrently during that check.
