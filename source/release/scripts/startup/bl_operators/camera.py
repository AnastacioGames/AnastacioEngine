# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty


# (left, bottom, right, top) ratios of the game window.
GAME_VIEWPORT_PRESETS = {
    'FULL': (0.0, 0.0, 1.0, 1.0),
    'LEFT': (0.0, 0.0, 0.5, 1.0),
    'RIGHT': (0.5, 0.0, 1.0, 1.0),
    'TOP': (0.0, 0.5, 1.0, 1.0),
    'BOTTOM': (0.0, 0.0, 1.0, 0.5),
    'TOP_LEFT': (0.0, 0.5, 0.5, 1.0),
    'TOP_RIGHT': (0.5, 0.5, 1.0, 1.0),
    'BOTTOM_LEFT': (0.0, 0.0, 0.5, 0.5),
    'BOTTOM_RIGHT': (0.5, 0.0, 1.0, 0.5),
    # 25% of the width and height, top right corner with a small margin.
    'PICTURE_IN_PICTURE': (0.73, 0.73, 0.98, 0.98),
}


class CAMERA_OT_game_viewport_preset(Operator):
    """Set the custom viewport ratios of the camera to a common layout"""
    bl_idname = "camera.game_viewport_preset"
    bl_label = "Custom Viewport Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(
        name="Preset",
        items=(
            ('FULL', "Full Screen", "Whole window"),
            ('LEFT', "Left", "Left half (split-screen)"),
            ('RIGHT', "Right", "Right half (split-screen)"),
            ('TOP', "Top", "Top half (split-screen)"),
            ('BOTTOM', "Bottom", "Bottom half (split-screen)"),
            ('TOP_LEFT', "Top Left", "Top left quarter"),
            ('TOP_RIGHT', "Top Right", "Top right quarter"),
            ('BOTTOM_LEFT', "Bottom Left", "Bottom left quarter"),
            ('BOTTOM_RIGHT', "Bottom Right", "Bottom right quarter"),
            ('PICTURE_IN_PICTURE', "Picture-in-Picture",
             "Small view in the top right corner (rear-view mirror, minimap)"),
        ),
    )

    @classmethod
    def poll(cls, context):
        return getattr(context, "camera", None) is not None

    def execute(self, context):
        viewport = context.camera.viewport
        (viewport.left_ratio, viewport.bottom_ratio,
         viewport.right_ratio, viewport.top_ratio) = GAME_VIEWPORT_PRESETS[self.preset]
        return {'FINISHED'}


classes = (
    CAMERA_OT_game_viewport_preset,
)
