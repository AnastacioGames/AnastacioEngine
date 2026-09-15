# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# The Original Code is Copyright (C) 2006, Blender Foundation
# All rights reserved.
#
# The Original Code is: all of this file.
#
# Contributor(s): Jacques Beaurain.
#
# ***** END GPL LICENSE BLOCK *****

set(INC
	.
	../blenkernel
	../blenlib
	../bmesh
	../imbuf
	../makesdna
	../makesrna

	# For node muting stuff...
	../nodes
	../nodes/intern

	../../../intern/glew-mx
	../../../intern/guardedalloc
	../../../intern/smoke/extern
)

set(INC_SYS
	${GLEW_INCLUDE_PATH}
)

set(SRC
	intern/gpu_basic_shader.c
	intern/gpu_buffers.c
	intern/gpu_codegen.c
	intern/gpu_compositing.c
	intern/gpu_debug.c
	intern/gpu_draw.c
	intern/gpu_extensions.c
	intern/gpu_framebuffer.c
	intern/gpu_init_exit.c
	intern/gpu_material.c
	intern/gpu_select.c
	intern/gpu_select_pick.c
	intern/gpu_select_sample_query.c
	intern/gpu_shader.c
	intern/gpu_texture.c
	intern/gpu_vertex_array.c

	GPU_basic_shader.h
	GPU_buffers.h
	GPU_compositing.h
	GPU_debug.h
	GPU_draw.h
	GPU_extensions.h
	GPU_framebuffer.h
	GPU_glew.h
	GPU_init_exit.h
	GPU_material.h
	GPU_select.h
	GPU_shader.h
	GPU_texture.h
	GPU_vertex_array.h
	intern/gpu_codegen.h
	intern/gpu_private.h
	intern/gpu_select_private.h
)

data_to_c_simple(shaders/gpu_shader_2d_box_vert.glsl SRC)

set(LIB ${BLENDER_GL_LIBRARIES})

# System GLEW is selected by the Linux runtime preset, so do not retain an
# unresolved dependency on the bundled extern_glew target. When system GLEW
# isn't used, link whichever bundled GLEW variant this configuration actually
# builds (desktop extern_glew, or extern_glew_es + bf_intern_glew_mx when
# WITH_GLEW_ES is on, e.g. the web-runtime preset) instead of hardcoding the
# desktop target, which has no library file when only the ES variant is built.
if(WITH_SYSTEM_GLEW)
	list(APPEND LIB ${GLEW_LIBRARY})
else()
	list(APPEND LIB ${BLENDER_GLEW_LIBRARIES})
endif()

data_to_c_simple(shaders/gpu_shader_geometry.glsl SRC)
data_to_c_simple(shaders/gpu_shader_flat_color_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_flat_color_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_frustum_line_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_frustum_solid_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_frustum_solid_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_light_glow_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_light_glow_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fire_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_smoke_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_smoke_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_material.glsl SRC)
data_to_c_simple(shaders/gpu_shader_sep_gaussian_blur_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_sep_gaussian_blur_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_basic_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_black_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_black_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_basic_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_basic_geom.glsl SRC)
data_to_c_simple(shaders/gpu_shader_frame_buffer_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_frame_buffer_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_vertex.glsl SRC)
data_to_c_simple(shaders/gpu_shader_vertex_world.glsl SRC)
data_to_c_simple(shaders/gpu_shader_vsm_store_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_vsm_store_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_ssao_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_dof_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_dof_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_dof_hq_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_dof_hq_vert.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_dof_hq_geo.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_bloom_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_tonemap_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_ssr_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_light_scatter_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_fxaa_frag.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_depth_resolve.glsl SRC)
data_to_c_simple(shaders/gpu_shader_fx_lib.glsl SRC)
data_to_c_simple(shaders/gpu_shader_lib.glsl SRC)

if(WITH_GAMEENGINE)
	add_definitions(-DWITH_GAMEENGINE)
endif()

if(WITH_MOD_SMOKE)
	add_definitions(-DWITH_SMOKE)
endif()

add_definitions(${GL_DEFINITIONS})

# The RangeRuntime CORE-profile build (WITH_GL_PROFILE_CORE_RANGERUNTIME) only needs
# the version/define injection point (gpu_shader.c), the builtin-matrix upload path
# (gpu_material.c), the uniform-declaration codegen (gpu_codegen.c, needs to skip
# re-declaring the 4 builtin matrix uniforms gpu_shader_material.glsl already declares
# unconditionally under core profile), and the blur-quad draw (gpu_framebuffer.c,
# migrated off glBegin/glEnd) to see WITH_GL_PROFILE_CORE -- the rest of this target
# (gpu_draw.c, gpu_buffers.c, gpu_compositing.c, gpu_select*.c, gpu_basic_shader.c,
# gpu_texture.c, gpu_extensions.c, gpu_debug.c) still uses immediate-mode/deprecated GL
# throughout and is not part of this migration's scope. Scoping the define to the whole
# target broke all of those; scope it per-file instead so the rest of bf_gpu stays on
# COMPAT even in this build.
if(WITH_GL_PROFILE_CORE_RANGERUNTIME)
	set_source_files_properties(
		intern/gpu_shader.c
		intern/gpu_material.c
		intern/gpu_codegen.c
		intern/gpu_framebuffer.c
		PROPERTIES COMPILE_DEFINITIONS "WITH_GL_PROFILE_CORE"
	)
endif()

if(WITH_IMAGE_DDS)
	add_definitions(-DWITH_DDS)
endif()

if(WITH_OPENSUBDIV)
	add_definitions(-DWITH_OPENSUBDIV)
endif()

blender_add_lib(bf_gpu "${SRC}" "${INC}" "${INC_SYS}" "${LIB}")
