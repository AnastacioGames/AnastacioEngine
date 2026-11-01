# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""File > Import > Fuse Character (.obj): turns an OBJ exported from Adobe Fuse into a game-ready character
(skeleton from the library, weights, texture atlas, LOD, ragdoll, group) without Mixamo.

The work runs in a background Blender so the open file is not touched; the finished Group<Name>.range is
then linked into the current scene as a group instance. Details: docs/personagem-auto-rig-plan.md."""

import os
import re
import subprocess

import bpy
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper


def _skeleton_items(self, context):
    import range_character_autorig as ar
    items = [(sid, name, folder) for sid, name, folder in ar.list_skeletons()]
    return items or [("NONE", "No skeleton library", "datafiles/characters is missing")]


class IMPORT_SCENE_OT_fuse_character(Operator, ImportHelper):
    """Create a game-ready character from an Adobe Fuse OBJ (skeleton, weights, atlas, LOD, ragdoll)"""
    bl_idname = "import_scene.fuse_character"
    bl_label = "Import Fuse Character"
    bl_options = {'REGISTER'}

    filename_ext = ".obj"
    filter_glob: StringProperty(default="*.obj", options={'HIDDEN'})

    skeleton: EnumProperty(name="Skeleton", items=_skeleton_items,
                            description="Skeleton from the library the character is built on")
    character_name: StringProperty(name="Name",
                                    description="Character name; the group is Group<Name> (empty: from the file)")
    ragdoll: BoolProperty(name="Ragdoll", default=True,
                           description="Add ragdoll boxes on the big bones (no hands or fingers)")
    output_dir: StringProperty(name="Output Folder", subtype='DIR_PATH',
                                description="Where Group<Name>.range and textures/ are written "
                                            "(empty: a folder next to the open file)")
    game_root: StringProperty(name="Game Folder", subtype='DIR_PATH',
                               description="Game project root, to attach its ragdoll component "
                                           "(empty: the folder of the open file)")
    link_group: BoolProperty(name="Add to Scene", default=True,
                              description="Link the finished group into the current scene at the 3D cursor")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "skeleton")
        layout.prop(self, "character_name")
        layout.prop(self, "ragdoll")
        layout.prop(self, "output_dir")
        layout.prop(self, "game_root")
        layout.prop(self, "link_group")

    def execute(self, context):
        if self.skeleton == "NONE":
            self.report({'ERROR'}, tip_("Skeleton library not found (datafiles/characters)"))
            return {'CANCELLED'}
        name = self.character_name.strip() or os.path.splitext(os.path.basename(self.filepath))[0]
        name = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or "Character"
        base = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.dirname(self.filepath)
        out_dir = bpy.path.abspath(self.output_dir) if self.output_dir else os.path.join(base, "Group" + name)
        root = bpy.path.abspath(self.game_root) if self.game_root else base
        cmd = [bpy.app.binary_path, "-b", "--factory-startup", "--python-expr",
               "import sys, range_character_autorig as ar; ar.cli_main(sys.argv[sys.argv.index('--') + 1:])",
               "--", self.filepath, name, out_dir, self.skeleton, "--projeto", root]
        if not self.ragdoll:
            cmd.append("--sem-ragdoll")
        window = context.window
        if window:
            window.cursor_set('WAIT')
        try:
            run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        finally:
            if window:
                window.cursor_set('DEFAULT')
        out = run.stdout + run.stderr
        path = os.path.join(out_dir, "Group%s.range" % name)
        if run.returncode != 0 or "PERSONAGEM" not in out or not os.path.isfile(path):
            tail = [l for l in out.splitlines() if l.strip()][-6:]
            print("\n".join(tail))
            self.report({'ERROR'}, tip_("Character creation failed (see the console)"))
            return {'CANCELLED'}
        for line in out.splitlines():
            if line.startswith("aviso"):
                self.report({'WARNING'}, line)
        if self.link_group:
            group_name = "Group" + name
            with bpy.data.libraries.load(path, link=True, relative=True) as (src, dst):
                dst.groups = [g for g in src.groups if g == group_name]
            if dst.groups and dst.groups[0]:
                inst = bpy.data.objects.new(group_name, None)
                inst.dupli_type = 'GROUP'
                inst.dupli_group = dst.groups[0]
                inst.location = context.scene.cursor_location
                context.scene.objects.link(inst)
        self.report({'INFO'}, tip_("Character saved: %s") % path)
        return {'FINISHED'}


classes = (
    IMPORT_SCENE_OT_fuse_character,
)
