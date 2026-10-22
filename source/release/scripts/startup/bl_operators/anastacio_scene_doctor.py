# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Game > Performance > Scene Doctor: looks at the open scene before playing and lists what will cost
load time, memory or frame time (big textures, heavy meshes without LoD, static objects outside the
Static Batch, triangle-mesh physics on moving bodies, big shadow buffers, big sounds, scripts that run
every frame). Each issue can select its objects and, when the change is safe, fix them in one click.

Rules are plain functions in RULES: rule(scene) returns a list of Issue; Issue.fix, when set, applies
the change. New checks only need a new function in that list."""

import json
import os
import time

import bpy
from bpy.props import IntProperty
from bpy.types import Operator, Panel

SEVERITY_ORDER = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
SEVERITY_ICON = {'HIGH': 'ERROR', 'MEDIUM': 'INFO', 'LOW': 'DOT'}

TEXTURE_BIG = 2048
TEXTURE_HUGE = 4096
MESH_HEAVY_TRIS = 50000
MESH_HUGE_TRIS = 200000
STATIC_TRIMESH_DENSE_TRIS = 20000
SHADOW_BUFFER_MAX = 2048
SHADOW_LAMPS_MANY = 4
SOUND_BIG_BYTES = 2 * 1024 * 1024
SOUND_STREAM_BYTES = 5 * 1024 * 1024


class Issue:
    __slots__ = ("rule", "key", "severity", "title", "detail", "objects", "fix")

    def __init__(self, rule, key, severity, title, detail="", objects=(), fix=None):
        self.rule = rule
        self.key = key
        self.severity = severity
        self.title = title
        self.detail = detail
        self.objects = list(objects)
        self.fix = fix

    def ident(self):
        return "%s:%s" % (self.rule, self.key)


# Last run: issues shown in the panel, the ones the user chose to ignore during this session, and the
# fixes applied (title, revert function) so they can be undone one by one.
_issues = []
_ignored = set()
_applied = []
_last_scene = ""


def _scene_objects(scene):
    """Every object of the scene: inactive layers hold what AddObject spawns during the game."""
    return list(scene.objects)


def _active_objects(scene, objects):
    layers = scene.layers
    return [ob for ob in objects if any(a and b for a, b in zip(ob.layers, layers))]


def _mesh_tris(mesh):
    return sum(len(p.vertices) - 2 for p in mesh.polygons)


def _subsurf_levels(ob):
    return sum(m.levels for m in ob.modifiers if m.type == 'SUBSURF' and m.show_viewport)


def _is_pot(n):
    return n > 0 and (n & (n - 1)) == 0


def _node_images(tree, images, visited):
    if tree is None or tree in visited:
        return
    visited.add(tree)
    for node in tree.nodes:
        image = getattr(node, "image", None)
        if image is not None:
            images.add(image)
        texture = getattr(node, "texture", None)
        if texture is not None and getattr(texture, "image", None) is not None:
            images.add(texture.image)
        if node.type == 'GROUP':
            _node_images(node.node_tree, images, visited)


def _scene_images(objects):
    """Images reached by the materials of the given objects: texture slots and node trees."""
    images = {}
    for ob in objects:
        for slot in ob.material_slots:
            ma = slot.material
            if ma is None:
                continue
            found = set()
            visited = set()
            for tslot in ma.texture_slots:
                if tslot and tslot.texture and getattr(tslot.texture, "image", None) is not None:
                    found.add(tslot.texture.image)
            if ma.use_nodes:
                _node_images(ma.node_tree, found, visited)
            for image in found:
                images.setdefault(image, set()).add(ob)
    return images


def _has_logic(ob):
    game = ob.game
    return bool(game.actuators) or bool(game.components) or any(c.type == 'PYTHON' for c in game.controllers)


def _is_animated(ob):
    ad = ob.animation_data
    return ad is not None and (ad.action is not None or len(ad.drivers) > 0)


def _vram_mb(w, h):
    return w * h * 4 * 4 / 3 / (1024 * 1024)


# ---------------------------------------------------------------------------
# Rules

def rule_textures(scene, objects):
    issues = []
    npot = []
    for image, users in _scene_images(objects).items():
        if image.type in {'RENDER_RESULT', 'COMPOSITING'}:
            continue
        w, h = image.size[0], image.size[1]
        if w == 0 or h == 0:
            continue
        side = max(w, h)
        if side > TEXTURE_BIG:
            issues.append(Issue(
                "texture_big", image.name, 'HIGH' if side >= TEXTURE_HUGE else 'MEDIUM',
                "Texture %s is %dx%d" % (image.name, w, h),
                "About %.0f MB of video memory without compression. %d or less is usually enough "
                "for game objects." % (_vram_mb(w, h), TEXTURE_BIG),
                sorted(users, key=lambda o: o.name)))
        if not (_is_pot(w) and _is_pot(h)):
            npot.append(image)
    if npot:
        names = ", ".join(sorted(i.name for i in npot)[:8])
        issues.append(Issue(
            "texture_npot", "all", 'LOW',
            "%d texture(s) with size not a power of two" % len(npot),
            "They cannot be stored compressed (DDS) and some GPUs resize them at load: %s" % names))
    return issues


def rule_heavy_meshes(scene, objects):
    issues = []
    seen = {}
    for ob in objects:
        if ob.type != 'MESH' or ob.data is None:
            continue
        if len(ob.lod_levels) > 1:
            continue
        mesh = ob.data
        if mesh not in seen:
            seen[mesh] = _mesh_tris(mesh)
        tris = seen[mesh] * (4 ** _subsurf_levels(ob))
        if tris < MESH_HEAVY_TRIS:
            continue
        detail = "No LoD levels; it is drawn with all triangles at any distance."
        if _subsurf_levels(ob):
            detail += " Subdivision Surface multiplies the mesh at game start."
        issues.append(Issue(
            "mesh_heavy", ob.name, 'HIGH' if tris >= MESH_HUGE_TRIS else 'MEDIUM',
            "%s has about %d triangles" % (ob.name, tris), detail, [ob]))
    return issues


def _static_batch_candidate(ob):
    if ob.type != 'MESH' or ob.use_static_batch:
        return False
    game = ob.game
    if game.physics_type not in {'STATIC', 'NO_COLLISION'}:
        return False
    if game.use_destruction or game.use_explosive or game.use_deform:
        return False
    if _is_animated(ob) or ob.parent is not None:
        return False
    if any(m.type in {'ARMATURE', 'MESH_DEFORM', 'HOOK'} for m in ob.modifiers):
        return False
    if ob.data.shape_keys is not None:
        return False
    # A LoD switch replaces the mesh of a batched object; keep them apart until that is handled.
    if len(ob.lod_levels) > 1:
        return False
    return True


def rule_static_batch(scene, objects):
    active = _active_objects(scene, objects)
    candidates = [ob for ob in active if _static_batch_candidate(ob)]
    safe = [ob for ob in candidates if not _has_logic(ob)]
    with_logic = [ob for ob in candidates if _has_logic(ob)]
    batched = sum(1 for ob in active if ob.type == 'MESH' and ob.use_static_batch)
    if not safe or len(safe) + batched < 2:
        return []

    groups = {}
    for ob in safe:
        ma = next((slot.material for slot in ob.material_slots if slot.material), None)
        groups.setdefault(ma.name if ma else "(no material)", []).append(ob)

    issues = []
    for name, obs in sorted(groups.items(), key=lambda g: -len(g[1])):
        if len(obs) < 2:
            continue  # one object per material: the batch would not save a draw call
        def fix(obs=obs):
            for ob in obs:
                ob.use_static_batch = True

            def revert():
                for ob in obs:
                    ob.use_static_batch = False
            return revert
        detail = ("They never move: Static Batch draws them together in one draw call instead of %d. "
                  "Check that no script moves them before fixing." % len(obs))
        issues.append(Issue(
            "static_batch", name, 'MEDIUM' if len(obs) >= 10 else 'LOW',
            "%d static object(s) with %s outside the Static Batch" % (len(obs), name), detail,
            sorted(obs, key=lambda o: o.name), fix))
    if with_logic:
        issues.append(Issue(
            "static_batch_logic", "all", 'LOW',
            "%d static object(s) with logic left out of the Static Batch" % len(with_logic),
            "They have logic bricks, scripts or components. Mark them by hand only if they never move.",
            sorted(with_logic, key=lambda o: o.name)))
    return issues


def rule_physics_shapes(scene, objects):
    issues = []
    for ob in objects:
        if ob.type != 'MESH':
            continue
        game = ob.game
        trimesh = game.use_collision_bounds and game.collision_bounds_type == 'TRIANGLE_MESH'
        if game.physics_type in {'DYNAMIC', 'RIGID_BODY', 'SOFT_BODY', 'CHARACTER'} and trimesh:
            def fix(ob=ob):
                ob.game.collision_bounds_type = 'CONVEX_HULL'

                def revert():
                    ob.game.collision_bounds_type = 'TRIANGLE_MESH'
                return revert
            issues.append(Issue(
                "physics_moving_trimesh", ob.name, 'HIGH',
                "%s moves with Triangle Mesh collision" % ob.name,
                "Triangle Mesh is meant for static scenery; on a moving body it is slow and collides "
                "badly. Convex Hull keeps the shape close and is much cheaper.", [ob], fix))
        elif game.physics_type == 'STATIC' and (trimesh or not game.use_collision_bounds):
            tris = _mesh_tris(ob.data) * (4 ** _subsurf_levels(ob))
            if tris >= STATIC_TRIMESH_DENSE_TRIS:
                issues.append(Issue(
                    "physics_dense_static", ob.name, 'LOW',
                    "%s collides with all its %d triangles" % (ob.name, tris),
                    "A simpler invisible collision mesh (or a box) would make physics cheaper.", [ob]))
    return issues


def rule_shadows(scene, objects):
    issues = []
    shadowed = [ob for ob in objects if ob.type == 'LAMP' and getattr(ob.data, "use_shadow", False)]
    for ob in shadowed:
        size = ob.data.shadow_buffer_size
        if size > SHADOW_BUFFER_MAX:
            def fix(lamp=ob.data, size=size):
                lamp.shadow_buffer_size = SHADOW_BUFFER_MAX

                def revert():
                    lamp.shadow_buffer_size = size
                return revert
            issues.append(Issue(
                "shadow_big", ob.name, 'MEDIUM',
                "%s has a %d shadow buffer" % (ob.name, size),
                "Every frame the scene is drawn into it again; %d is usually sharp enough." % SHADOW_BUFFER_MAX,
                [ob], fix))
    spots = [ob for ob in shadowed if ob.data.type in {'SPOT', 'POINT', 'AREA'}]
    if len(spots) > SHADOW_LAMPS_MANY:
        issues.append(Issue(
            "shadow_many", "all", 'MEDIUM',
            "%d lamps cast shadows" % len(spots),
            "Each shadow lamp draws the scene once more per frame. Keep shadows on the lamps that "
            "matter and turn off the rest.", sorted(spots, key=lambda o: o.name)))
    return issues


def _sound_bytes(sound):
    if sound.packed_file:
        return sound.packed_file.size
    try:
        return os.path.getsize(bpy.path.abspath(sound.filepath, library=sound.library))
    except OSError:
        return 0


def rule_sounds(scene, objects):
    issues = []
    for sound in bpy.data.sounds:
        if sound.users - int(sound.use_fake_user) <= 0:
            continue
        size = _sound_bytes(sound)
        if size >= SOUND_STREAM_BYTES and sound.use_memory_cache:
            def fix(sound=sound):
                sound.use_memory_cache = False

                def revert():
                    sound.use_memory_cache = True
                return revert
            issues.append(Issue(
                "sound_cached", sound.name, 'MEDIUM',
                "Sound %s (%.1f MB) is fully loaded in memory" % (sound.name, size / 1048576),
                "Long music or ambience can play streamed from the file instead of held in memory "
                "(decoding then costs some CPU while playing). Takes effect after the file is reopened.",
                fix=fix))
        elif size >= SOUND_BIG_BYTES and sound.filepath.lower().endswith(".wav"):
            issues.append(Issue(
                "sound_wav", sound.name, 'LOW',
                "Sound %s is a %.1f MB WAV" % (sound.name, size / 1048576),
                "OGG makes the game smaller and faster to load with no audible difference."))
    return issues


def rule_scripts_every_frame(scene, objects):
    busy = []
    for ob in objects:
        for cont in ob.game.controllers:
            if cont.type != 'PYTHON':
                continue
            for sens in ob.game.sensors:
                if any(c == cont for c in sens.controllers) and sens.type == 'ALWAYS' and \
                        sens.use_pulse_true_level and sens.tick_skip == 0:
                    busy.append(ob)
                    break
            else:
                continue
            break
    if not busy:
        return []
    return [Issue(
        "scripts_every_frame", "all", 'LOW',
        "%d object(s) run a script every frame" % len(busy),
        "Always + True Level with Skip 0 runs the script 60 times a second. If it does not need to, "
        "raise Skip or run it on an event.", sorted(busy, key=lambda o: o.name))]


RULES = (
    rule_textures,
    rule_heavy_meshes,
    rule_static_batch,
    rule_physics_shapes,
    rule_shadows,
    rule_sounds,
    rule_scripts_every_frame,
)


def diagnose(scene):
    objects = _scene_objects(scene)
    issues = []
    for rule in RULES:
        try:
            issues.extend(rule(scene, objects))
        except Exception as ex:
            issues.append(Issue(rule.__name__, "error", 'HIGH', "Check %s failed: %s" % (rule.__name__, ex)))
    issues.sort(key=lambda i: (SEVERITY_ORDER[i.severity], i.rule, i.key))
    return issues


def _write_json(scene, issues):
    from bl_operators.anastacio_performance_report import reports_dir
    name = bpy.path.display_name_from_filepath(bpy.data.filepath) or "untitled"
    path = os.path.join(reports_dir(), "scene_doctor_%s.json" % bpy.path.clean_name(name))
    data = {
        "file": bpy.data.filepath,
        "scene": scene.name,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "issues": [{"rule": i.rule, "key": i.key, "severity": i.severity, "title": i.title,
                    "detail": i.detail, "objects": [o.name for o in i.objects],
                    "fixable": i.fix is not None} for i in issues],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return path


def _visible_issues():
    return [i for i in _issues if i.ident() not in _ignored]


def _run(context):
    global _issues, _last_scene
    _issues = diagnose(context.scene)
    _last_scene = context.scene.name
    return _visible_issues()


# ---------------------------------------------------------------------------
# Operators and panel

class GAME_OT_scene_doctor(Operator):
    """Check the scene for what costs load time, memory or frame time, with one-click fixes"""
    bl_idname = "game.scene_doctor"
    bl_label = "Scene Doctor"

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        issues = _run(context)
        try:
            _write_json(context.scene, issues)
        except OSError:
            pass
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                area.spaces.active.context = 'SCENE'
                area.tag_redraw()
        if issues:
            self.report({'INFO'}, "Scene Doctor: %d issue(s), see Properties > Scene" % len(issues))
        else:
            self.report({'INFO'}, "Scene Doctor: nothing to improve")
        return {'FINISHED'}


def _issue_at(index):
    issues = _visible_issues()
    return issues[index] if 0 <= index < len(issues) else None


class GAME_OT_scene_doctor_select(Operator):
    """Select the objects of this issue"""
    bl_idname = "game.scene_doctor_select"
    bl_label = "Select"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        issue = _issue_at(self.index)
        if issue is None or not issue.objects:
            return {'CANCELLED'}
        for ob in context.scene.objects:
            ob.select = False
        for ob in issue.objects:
            if ob.name in context.scene.objects:
                ob.select = True
        context.scene.objects.active = issue.objects[0]
        return {'FINISHED'}


class GAME_OT_scene_doctor_fix(Operator):
    """Apply the suggested change for this issue"""
    bl_idname = "game.scene_doctor_fix"
    bl_label = "Fix"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        issue = _issue_at(self.index)
        if issue is None or issue.fix is None:
            return {'CANCELLED'}
        revert = issue.fix()
        if revert is not None:
            _applied.append((issue.title, revert))
        self.report({'INFO'}, "Fixed: %s" % issue.title)
        _run(context)
        return {'FINISHED'}


class GAME_OT_scene_doctor_revert(Operator):
    """Undo this fix"""
    bl_idname = "game.scene_doctor_revert"
    bl_label = "Revert"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        if not 0 <= self.index < len(_applied):
            return {'CANCELLED'}
        title, revert = _applied.pop(self.index)
        try:
            revert()
        except ReferenceError:
            self.report({'WARNING'}, "Could not revert, the data no longer exists: %s" % title)
            return {'CANCELLED'}
        self.report({'INFO'}, "Reverted: %s" % title)
        _run(context)
        return {'FINISHED'}


class GAME_OT_scene_doctor_ignore(Operator):
    """Hide this issue until Blender is restarted"""
    bl_idname = "game.scene_doctor_ignore"
    bl_label = "Ignore"

    index: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        issue = _issue_at(self.index)
        if issue is None:
            return {'CANCELLED'}
        _ignored.add(issue.ident())
        return {'FINISHED'}


class SCENE_PT_scene_doctor(Panel):
    bl_label = "Scene Doctor"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def draw(self, context):
        layout = self.layout
        layout.operator("game.scene_doctor", text="Check Scene", icon='VIEWZOOM')

        if _applied:
            box = layout.box()
            box.label(text="Applied fixes")
            for index, (title, _revert) in enumerate(_applied):
                row = box.row(align=True)
                row.label(text=title, icon='FILE_TICK')
                row.operator("game.scene_doctor_revert", text="Revert").index = index

        if _last_scene != context.scene.name:
            layout.label(text="Not checked yet")
            return
        issues = _visible_issues()
        if not issues:
            layout.label(text="Nothing to improve", icon='FILE_TICK')
            return

        for index, issue in enumerate(issues):
            box = layout.box()
            row = box.row(align=True)
            row.label(text=issue.title, icon=SEVERITY_ICON[issue.severity])
            if issue.objects:
                row.operator("game.scene_doctor_select", text="", icon='RESTRICT_SELECT_OFF').index = index
            if issue.fix is not None:
                row.operator("game.scene_doctor_fix", text="Fix").index = index
            row.operator("game.scene_doctor_ignore", text="", icon='X').index = index
            if issue.detail:
                col = box.column(align=True)
                col.scale_y = 0.8
                for line in _wrap(issue.detail, 70):
                    col.label(text=line)


def _wrap(text, width):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = word if not line else line + " " + word
    if line:
        lines.append(line)
    return lines


classes = (
    GAME_OT_scene_doctor,
    GAME_OT_scene_doctor_select,
    GAME_OT_scene_doctor_fix,
    GAME_OT_scene_doctor_revert,
    GAME_OT_scene_doctor_ignore,
    SCENE_PT_scene_doctor,
)
