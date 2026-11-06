# Motion Recording (Rec Play): settings saved in the .blend as ID properties.
# Plan: docs/gravacao-de-movimento-plan.md. The Rec Play operator and the C++
# capture come in later phases; the runtime will read these by name.

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
                       StringProperty)
from bpy.types import Operator, PropertyGroup, UIList


class RecTakeActor(PropertyGroup):
    object_name = StringProperty(name="Object")
    action_name = StringProperty(name="Action")
    # Start of the names of its NLA tracks, on armatures.
    track_prefix = StringProperty(name="NLA Tracks")


class RecTake(PropertyGroup):
    # Written by view3d_motion_record.c. A take groups the Actions of one recording.
    duration = FloatProperty(name="Duration")
    actors = CollectionProperty(type=RecTakeActor)


def _take_tracks(actor):
    ob = bpy.data.objects.get(actor.object_name)
    if not ob or not ob.animation_data:
        return ob, ()
    return ob, [t for t in ob.animation_data.nla_tracks if t.name.startswith("Rec_")]


class SCENE_UL_rec_takes(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon='REC')
        row.label(text="%.1f s, %d actor(s)" % (item.duration, len(item.actors)))


class SCENE_OT_rec_take_remove(Operator):
    """Delete this take and its Actions"""
    bl_idname = "scene.rec_take_remove"
    bl_label = "Delete Take"

    index = IntProperty(default=-1, options={'HIDDEN'})

    def execute(self, context):
        scene = context.scene
        index = self.index if self.index >= 0 else scene.ae_rec_take_index
        if not 0 <= index < len(scene.ae_rec_takes):
            return {'CANCELLED'}
        for actor in scene.ae_rec_takes[index].actors:
            action = bpy.data.actions.get(actor.action_name)
            if action:
                bpy.data.actions.remove(action, do_unlink=True)
            if actor.track_prefix:
                ob, tracks = _take_tracks(actor)
                for track in tracks:
                    if track.name.startswith(actor.track_prefix):
                        ob.animation_data.nla_tracks.remove(track)
        scene.ae_rec_takes.remove(index)
        scene.ae_rec_take_index = max(0, len(scene.ae_rec_takes) - 1)
        return {'FINISHED'}

    def invoke(self, context, event):
        # Rec Play calls execute inside its own undo step; only the button adds one.
        result = self.execute(context)
        bpy.ops.ed.undo_push(message=self.bl_label)
        return result


class SCENE_OT_rec_take_use(Operator):
    """Put this take on its actors and set the scene range to its length"""
    bl_idname = "scene.rec_take_use"
    bl_label = "Use Take"
    bl_options = {'UNDO'}

    def execute(self, context):
        scene = context.scene
        index = scene.ae_rec_take_index
        if not 0 <= index < len(scene.ae_rec_takes):
            return {'CANCELLED'}
        take = scene.ae_rec_takes[index]
        for actor in take.actors:
            ob = bpy.data.objects.get(actor.object_name)
            action = bpy.data.actions.get(actor.action_name)
            if ob and action:
                if not ob.animation_data:
                    ob.animation_data_create()
                ob.animation_data.action = action
            if actor.track_prefix:
                for track in _take_tracks(actor)[1]:
                    track.mute = not track.name.startswith(actor.track_prefix)
        scene.frame_end = scene.frame_start + int(take.duration * scene.render.fps + 0.5)
        scene.frame_set(scene.frame_start)
        return {'FINISHED'}


class SCENE_OT_rec_take_to_cutscene(Operator):
    """Add a Play Take event to the active cutscene sequence, after the takes already there"""
    bl_idname = "scene.rec_take_to_cutscene"
    bl_label = "Add to Cutscene"
    bl_options = {'UNDO'}

    def execute(self, context):
        scene = context.scene
        index = scene.ae_rec_take_index
        if not 0 <= index < len(scene.ae_rec_takes):
            return {'CANCELLED'}
        take = scene.ae_rec_takes[index]
        settings = scene.cutscene_settings
        if not settings.sequences:
            bpy.ops.cutscene.sequence_add()
        sequence_index = min(settings.active_sequence_index, len(settings.sequences) - 1)
        sequence = settings.sequences[sequence_index]
        start = 0.0
        for event in sequence.events:
            length = 0.0
            if event.type == 'PLAY_TAKE':
                other = scene.ae_rec_takes.get(event.take_name)
                length = other.duration if other else 0.0
            start = max(start, event.time + length)
        bpy.ops.cutscene.event_add(sequence_index=sequence_index)
        event = sequence.events[-1]
        event.type = 'PLAY_TAKE'
        event.name = take.name
        event.take_name = take.name
        event.time = start
        self.report({'INFO'}, "%s added to %s at %.1f s" % (take.name, sequence.name, start))
        return {'FINISHED'}


# bl_operators.register() reads this list from every module.
classes = (RecTakeActor, RecTake, SCENE_UL_rec_takes, SCENE_OT_rec_take_remove, SCENE_OT_rec_take_use,
           SCENE_OT_rec_take_to_cutscene)


def register_props():
    S = bpy.types.Scene
    S.ae_rec_takes = CollectionProperty(type=RecTake)
    S.ae_rec_take_index = IntProperty(name="Active Take", default=0, min=0)
    S.ae_rec_take_counter = IntProperty(default=0, options={'HIDDEN'})
    S.ae_rec_track_counter = IntProperty(default=0, options={'HIDDEN'})
    S.ae_rec_replace_take = BoolProperty(name="Replace Selected Take", default=False,
        description="The new recording takes the place of the selected take instead of adding one")
    S.ae_rec_max_duration = FloatProperty(name="Max Duration (s)", default=0.0, min=0.0, max=3600.0,
        description="Recording stops by itself after this many seconds (0 = until F10)")
    S.ae_rec_countdown = IntProperty(name="Countdown", default=3, min=0, max=10,
        description="Seconds counted on screen before recording starts (0 = start at once)")
    # Enum numbers will be read by C++ from the IDProperty: keep 0/1.
    S.ae_rec_walk_speed = FloatProperty(name="Walk Speed", default=3.0, min=0.1, max=50.0,
                                        description="Meters per second of WASD on an actor with no logic")
    S.ae_rec_walk_negative_y = BoolProperty(name="Faces -Y", default=False,
                                            description="The character looks along -Y, so W walks that way")
    S.ae_rec_sample_rate = EnumProperty(name="Sampling", default='FRAME', items=(
        ('FRAME', "Every Frame", "One sample per logic frame", 0),
        ('FIXED', "Fixed Rate", "Samples at the rate below, independent of the frame rate", 1),
    ), description="How often the actors are sampled while recording")
    S.ae_rec_fixed_rate = IntProperty(name="Rate", default=30, min=1, max=240,
        description="Samples per second when Sampling is Fixed Rate")
    S.ae_rec_make_keyframes = BoolProperty(name="Generate Keyframes", default=True,
        description="When recording stops, convert the take into an editable Action per actor")
    S.ae_rec_keyframe_tolerance = FloatProperty(name="Simplify", default=0.001, min=0.0, max=1.0,
        precision=4, description="Keyframes that change less than this are removed (0 = keep every sample)")
    S.ae_rec_record_camera = BoolProperty(name="Record Active Camera", default=False,
        description="Also record the active camera as an actor")
    S.ae_rec_playback_layers = BoolProperty(name="Play Other Takes", default=True,
        description="Actors not being recorded replay their active take, so takes stack in layers")
    S.ae_rec_playback_collision = BoolProperty(name="Collide on Replay", default=False,
        description="Replaying actors keep colliding with the scene (off = kinematic)")
    S.ae_rec_show_advanced = BoolProperty(name="Advanced", default=False,
        description="Show the detailed recording options")
    bpy.types.Object.ae_rec_action = StringProperty(name="Action",
        description="Animation played while you move the character (empty = its own game controls)")
    bpy.types.Object.ae_rec_actor = BoolProperty(name="Record Actor", default=False,
        description="Record this object when Rec Play is used (none marked = the active object)")


def unregister_props():
    for name in ('countdown', 'sample_rate', 'fixed_rate', 'make_keyframes', 'keyframe_tolerance',
                 'record_camera', 'playback_layers', 'playback_collision', 'show_advanced',
                 'takes', 'take_index', 'take_counter', 'track_counter', 'replace_take', 'max_duration'):
        delattr(bpy.types.Scene, 'ae_rec_' + name)
    del bpy.types.Object.ae_rec_actor
    del bpy.types.Object.ae_rec_action
