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
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_ConsoleWindow.h
 *  \ingroup ketsji
 */

#ifndef KX_CONSOLEWINDOW_H
#define KX_CONSOLEWINDOW_H

#include <string>

/** In-game ImGui window mirroring the engine's log (CM_Error/CM_Warning/...)
 *  so the user doesn't need to keep an external console open. */
class KX_ConsoleWindow
{
 private:
  bool m_autoScroll;
  char m_filter[128];

 public:
  KX_ConsoleWindow();
  ~KX_ConsoleWindow();

  /// Draws the console window. Call every frame while the console is shown.
  void Render();
};

#endif  // KX_CONSOLEWINDOW_H
