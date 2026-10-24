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

# <pep8 compliant>

# The Game panels live in properties_game_*.py, one file per editor tab.
# This module keeps the public names (flowmenu imports them) and the
# registration order of `classes`, which sets the panel order in the UI.

import bpy
from bpy.props import EnumProperty
from .properties_game_object import *  # noqa
from .properties_game_physics import *  # noqa
from .properties_game_render import *  # noqa
from .properties_game_scene import *  # noqa
from .properties_game_world import *  # noqa
from .properties_game_light import *  # noqa

classes = (
    LOGIC_OT_component_field_tool,
GAME_PT_game_components,
    LOGIC_OT_component_editor_button,
    GAME_PT_game_properties,
    PHYSICS_PT_game_category,
    PHYSICS_PT_game_physics,
    PHYSICS_PT_game_collision_bounds,
    PHYSICS_PT_game_obstacles,
    PHYSICS_PT_game_destruction,
    PHYSICS_PT_game_explosive,
    PHYSICS_PT_game_deform,
    RENDER_OT_set_game_resolution,
    RENDER_OT_game_vr_setup,
    RENDER_MT_game_res_embedded,
    RENDER_MT_game_res_player,
    RENDER_MT_game_target_fps,
    RENDER_MT_game_animation_fps,
    RENDER_MT_game_bit_depth,
    RENDER_MT_game_refresh_rate,
    RENDER_PT_game_cook,
    RENDER_PT_embedded,
    RENDER_PT_game_display,
    RENDER_PT_game_vr,
    RENDER_PT_game_shading,
    RENDER_PT_game_ssgi,
    RENDER_PT_game_baked_lighting,
    RENDER_PT_game_post_process_shaders,
    RENDER_PT_game_system,
    RENDER_PT_game_attachments,
    RENDER_PT_game_animations,
	RENDER_UL_attachments,
    SCENE_PT_game_physics,
    SCENE_PT_export_category,
    SCENE_PT_game_network,
    SCENE_PT_game_navmesh,
    WORLD_PT_game_context_world,
    WORLD_PT_game_world,
    WORLD_PT_game_environment_lighting,
    WORLD_PT_game_mist,
    DATA_PT_shadow_game,
    DATA_PT_shadow_csm_game,
    DATA_PT_light_culling_game,
    OBJECT_MT_lod_tools,
    OBJECT_OT_game_load_with_scene,
    OBJECT_OT_bake_lod_impostor,
    OBJECT_PT_levels_of_detail,
    OBJECT_PT_game_object_tasks,
    OBJECT_MT_culling,
    OBJECT_PT_game_network,
    OBJECT_PT_activity_culling,
    OBJECT_PT_animation_events,
)

bpy.types.Scene.show_expanded_game_cursor = bpy.props.BoolProperty(name="Expanded", default=False)

# Smart Components: which objects run Editor.draw_gizmo in the viewport.
bpy.types.WindowManager.range_component_gizmos = EnumProperty(
    name="Component Gizmos",
    description="Viewport drawing of Smart Components (Editor.draw_gizmo) and of the logic bricks (Near, Radar, Ray, Steering, Track To, Camera)",
    items=(
        ('OFF', "Off", "Don't draw component gizmos"),
        ('SELECTED', "Selected", "Draw gizmos of the selected objects"),
        ('ALL', "All", "Draw gizmos of every visible object"),
    ),
    default='SELECTED',
)

try:
    import range_component_editor
    range_component_editor.enable_gizmos()
except Exception as e:
    print("Component gizmos:", e)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
