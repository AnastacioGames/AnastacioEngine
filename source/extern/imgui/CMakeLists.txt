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
# Contributor(s): Range Engine
#
# ***** END GPL LICENSE BLOCK *****

set(INC
	include/backend
	include
)

set(INC_SYS

)

set(SRC
	src/backend/imgui_impl_opengl3.cpp
	src/imgui.cpp
	src/imgui_demo.cpp
	src/imgui_draw.cpp
	src/imgui_tables.cpp
	src/imgui_widgets.cpp
	
	include/backend/imgui_impl_opengl3.h
	include/backend/imgui_impl_opengl3_loader.h
	include/IconsForkAwesome.h
	include/imconfig.h
	include/imgui.h
	include/imgui_internal.h
	include/imstb_rectpack.h
	include/imstb_textedit.h
	include/imstb_truetype.h
)

set(LIB
)

blender_add_lib(extern_imgui "${SRC}" "${INC}" "${INC_SYS}" "${LIB}")
