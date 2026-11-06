# Motion Recording (Rec Play): settings saved in the .blend as ID properties.
# Plan: docs/gravacao-de-movimento-plan.md. The Rec Play operator and the C++
# capture come in later phases; the runtime will read these by name.

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty


def register_props():
    S = bpy.types.Scene
    S.ae_rec_countdown = IntProperty(name="Countdown", default=3, min=0, max=10,
        description="Seconds counted on screen before recording starts (0 = start at once)")
    # Enum numbers will be read by C++ from the IDProperty: keep 0/1.
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
                 'record_camera', 'playback_layers', 'playback_collision', 'show_advanced'):
        delattr(bpy.types.Scene, 'ae_rec_' + name)
    del bpy.types.Object.ae_rec_actor
    del bpy.types.Object.ae_rec_action
