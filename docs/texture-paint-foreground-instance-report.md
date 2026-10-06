# Texture Paint: freeze over foreground group instance

Date: 2026-10-06

## User-visible behavior

The active object being painted is a mesh behind a different object. While holding the paint button and moving the cursor from the active mesh across the foreground instance `CKP_LinhaDeChegada`, the editor becomes unresponsive and memory grows until it eventually recovers or closes.

This is not a click on the foreground object to start a new stroke. It is one already active texture-paint stroke that crosses the foreground instance.

## Captured evidence

- Session log: `debug-logs/RangeEngine-paint-empty-guard-20261006-062210.log.txt` (intentionally untracked).
- During the reproduction, `RangeEngine.exe` stopped responding and its private memory reached about 8.7 GB.
- The final log section is dominated by repeated `BKE_undosys_stack_init_or_active_with_type: type='Image'` messages while `PAINT_OT_image_paint` remains active. This is consistent with repeated image-undo tile allocation/update during the stalled stroke.
- No GPU error or Python traceback was produced in this session.

## Relevant .range configuration

Read from `D:\ProjetoRolimaRacer\RolimaRacer.range` with `RangeEngine.exe --background`:

- `CKP_LinhaDeChegada`: an `EMPTY` that instances group `CKP_LinhaDeChegada`; it has `NO_COLLISION` and no components, sensors, controllers, or actuators.
- Group `CKP_LinhaDeChegada` contains `LinhadeChegada` and `Group_add_player`.
- `LinhadeChegada`: a `MESH` configured as `STATIC`, with collision bounds `BOX`, `Actor` and `Ghost` enabled. It owns six Python component definitions: `scripts.checkpoint`, `scripts.time.time_of_racer`, `scripts.AddOverlayScene`, `scripts.effects.main_pool_manager`, `scripts.camera_system.add_cameras`, and `scripts.optimized_lights`.
- `Group_add_player`: an `EMPTY` parented to `LinhadeChegada`, with no collision, components, sensors, controllers, or actuators.
- No logic-brick collision sensor exists on either of those two objects in the inspected file. The game components do not execute while editing/painting; their viewport script icon is only an overlay draw call.

## Technical diagnosis

The texture-paint face lookup calls `ED_view3d_backbuf_sample()`. Its backing selection pass draws only the active object (`backdrawview3d()` calls `draw_object_backbufsel()` for `obact`). Therefore it can report a valid face of the painted object even when a foreign mesh or group instance is visually in front of that face.

This explains why the current active-face guards do not recognize `CKP_LinhaDeChegada` as an obstruction. It also means collision settings, sensors, and Python components are not the direct editor-side trigger. The most likely failure is that projection painting continues to produce image undo work while passing through foreground geometry, until accumulated work/memory makes the UI appear frozen.

This remains a diagnosis, not a final root-cause proof: the exact allocation site needs a focused memory trace or instrumentation around image undo tiles.

## Changes already made

Commit `fff04797` (`Fix texture paint freezes over non-painted objects`) contains:

- `source/source/blender/gpu/intern/gpu_codegen.c`: initialize optimized-out `GPUInput.shaderloc` to `-1` and skip invalid uniform uploads, removing a prior `GL_INVALID_OPERATION` flood.
- `source/source/blender/editors/sculpt_paint/paint_image_proj.c`: enlarge the clipping point buffer from 8 to 13 entries to prevent stack corruption; stop projected paint when its active-surface face pick fails.
- `source/source/blender/editors/sculpt_paint/paint_image.c`: reject a new 3D texture-paint stroke outside the active mesh and skip stroke updates when the active-object backbuffer has no face.

The editor rebuilt successfully after these changes. They reduce freezes over empty space and invalid paint starts, but cannot distinguish a foreground object from the painted mesh behind it because the current backbuffer is active-object-only.

## Recommended next investigation

1. Instrument `ED_image_undo_push_tile()` and related tile allocation in `paint_image_undo.c` to record image name, tile coordinates, byte count, and cumulative tile count for one stroke. Confirm the growth source before changing undo policy.
2. Build a foreground-occlusion test for texture paint using the full viewport object selection pass or `ED_transform_snap_object_context` ray casting. A stroke update should be skipped when the nearest visible mesh is not the active paint object.
3. Preserve normal painting through empty space where desired; the new occlusion rule must only reject a real mesh instance in front of the active surface, not an Empty icon or component overlay alone.
4. Reproduce with a minimal scene: one paintable plane behind one instanced group containing a mesh, then compare with the group instance hidden and with its mesh hidden.
