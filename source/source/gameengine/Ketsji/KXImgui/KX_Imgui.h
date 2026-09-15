/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 *
 * The Original Code is Copyright (C) 2022-2023 by Range Engine.
 *
 * The Original Code is: all of this file.
 *
 * ***** END GPL LICENSE BLOCK *****
 *
 */

 /** \file KXImgui/KX_Imgui.h
  *  \ingroup ketsji
  */

#ifndef KX_IMGUI_H
#  define KX_IMGUI_H

#include <fstream>
#include <sstream>

#include <string>
#include "DEV_InputDevice.h"

#include "implot.h" // already has imgui.h

class KX_GameObject;

class KX_Imgui
{
public:
	KX_Imgui();
	~KX_Imgui();

	void Init(DEV_InputDevice *inputDevice);
	void NextFrame();
	void ProcessInputEvents();
	void Render();
	void Stop();

	// imgui.ini disk location.
	std::string imguiConfigPath;

	/// Custom Save/Load System. call PrepareToSaveSection >> WriteValues ... >> CloseSection()
	std::ofstream streamImguiConfig_Write;
	std::ifstream streamImguiConfig_Read;
	bool streamImguiConfig_Open; // Shared with Write/Read. It is not allowed to do both at the same time!

	void		OpenImgui_Config_ToSave(const char *sectionName);

	void		WriteIntValue(const char *name, int intValue);
	void		WriteFloatValue(const char *name, float floatValue);
	void		WriteBoolValue(const char *name, bool boolValue);
	void		WriteCharValue(const char *name, char charValue);

	void		SaveAndCloseImgui_Config();

	/// Load Custom Save/Load System. OpenImgui_ToLoad >> LoadSection_Config >> GetValues ... >> CloseImgui_Config
	// WARNING: Keep the loading in sync! the same as for blender read/write file ...
	void		OpenImgui_Config_ToLoad();

	bool		LoadSection_Config(std::string SectionName);
	int			LoadIntValue();
	float		LoadFloatValue();
	bool		LoadBoolValue();
	std::string	LoadStringValue();

	void		CloseImgui_Config();
};

void DrawCustomCursor();
void SetupDebugModeStyle();

#endif // KX_IMGUI_H
