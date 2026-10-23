# Sprite → voxel workbench

## First release
Implemented and verified on 2026-10-23.

1. Define one consistent coordinate system and six orthographic cameras.
2. Ingest transparent PNG views or explicitly labeled square sheet cells.
3. Intersect silhouettes, initialize colors, and report projection mismatch.
4. Provide a local browser workbench with orbit, slice painting, undo, and exports.
5. Expose the running workbench to MCP agents, including image comparisons.
6. Verify geometry, carving, edits, persistence, HTTP, and MCP integration.

## Deliberate boundaries
Orthographic, aligned, square frames only; no inferred camera angles. Alpha >=128
means occupied. Colored pixels are opaque voxels. Camera views cannot determine
hidden cavities or unique topology. Inconsistent colors across views can remain
unmatchable. The connected MCP client supplies the reasoning model; no simulated
AI loop or embedded API key is required.

## Follow-on work
Camera calibration for isometric sprites, rectangular volumes, region editing,
MagicaVoxel/glTF exports, and a bounded model-provider loop with checkpoint rollback.
