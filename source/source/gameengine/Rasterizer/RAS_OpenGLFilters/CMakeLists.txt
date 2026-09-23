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
# The Original Code is: all of this file.
#
# Contributor(s): Range Engine.
# ***** END GPL LICENSE BLOCK *****

set(INC
)

set(INC_SYS
)

set(SRC
)

set(LIB
)

data_to_c_simple(RAS_Bloom2DFilter_buf.glsl SRC)
data_to_c_simple(RAS_Bloom2DFilter_bufH.glsl SRC)
data_to_c_simple(RAS_Bloom2DFilter_bufV.glsl SRC)
data_to_c_simple(RAS_Bloom2DFilter_Image.glsl SRC)
data_to_c_simple(RAS_Tonemaps2DFilter.glsl SRC)
data_to_c_simple(RAS_LightScaterring_Buffer2DFilter.glsl SRC)
data_to_c_simple(RAS_LightScaterring_Image2DFilter.glsl SRC)
data_to_c_simple(RAS_SSR2DFilter.glsl SRC)
data_to_c_simple(RAS_SSR_Blur2DFilter.glsl SRC)
data_to_c_simple(RAS_SSAO2DFilter.glsl SRC)
data_to_c_simple(RAS_Blur2DFilter.glsl SRC)
data_to_c_simple(RAS_Dilation2DFilter.glsl SRC)
data_to_c_simple(RAS_Erosion2DFilter.glsl SRC)
data_to_c_simple(RAS_Fxaa2DFilter.glsl SRC)
data_to_c_simple(RAS_GrayScale2DFilter.glsl SRC)
data_to_c_simple(RAS_Invert2DFilter.glsl SRC)
data_to_c_simple(RAS_Laplacian2DFilter.glsl SRC)
data_to_c_simple(RAS_Prewitt2DFilter.glsl SRC)
data_to_c_simple(RAS_Sepia2DFilter.glsl SRC)
data_to_c_simple(RAS_OutLine2DFilter.glsl SRC)
data_to_c_simple(RAS_Sharpen2DFilter.glsl SRC)
data_to_c_simple(RAS_Sobel2DFilter.glsl SRC)
data_to_c_simple(RAS_VertexShader2DFilter.glsl SRC)
data_to_c_simple(RAS_Rain2DFilter.glsl SRC)
data_to_c_simple(RAS_Clouds2DFilter.glsl SRC)
data_to_c_simple(RAS_LensFlare2DFilter.glsl SRC)

blender_add_lib(ge_rasterizer_shaders "${SRC}" "${INC}" "${INC_SYS}" "${LIB}")
