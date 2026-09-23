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

/** \file KX_ConsoleWindow.cpp
 *  \ingroup ketsji
 */

#include "KX_ConsoleWindow.h"

#include "implot.h"  // already has imgui.h

#include "CM_LogBuffer.h"

KX_ConsoleWindow::KX_ConsoleWindow() : m_autoScroll(true)
{
  m_filter[0] = '\0';
}

KX_ConsoleWindow::~KX_ConsoleWindow()
{
}

static ImVec4 GetLevelColor(CM_LogLevel level)
{
  switch (level) {
    case CM_LogLevel::ERROR_:
      return ImVec4(0.90f, 0.30f, 0.30f, 1.0f);
    case CM_LogLevel::WARNING:
      return ImVec4(0.90f, 0.80f, 0.20f, 1.0f);
    case CM_LogLevel::DEBUG:
      return ImVec4(0.60f, 0.60f, 0.60f, 1.0f);
    case CM_LogLevel::MESSAGE:
    default:
      return ImVec4(0.85f, 0.85f, 0.85f, 1.0f);
  }
}

void KX_ConsoleWindow::Render()
{
  if (!ImGui::Begin("Console")) {
    ImGui::End();
    return;
  }

  if (ImGui::Button("Clear")) {
    CM_LogBuffer::Get().Clear();
  }
  ImGui::SameLine();
  ImGui::Checkbox("Auto-scroll", &m_autoScroll);
  ImGui::SameLine();
  ImGui::SetNextItemWidth(200.0f);
  ImGui::InputText("Filter", m_filter, sizeof(m_filter));

  ImGui::Separator();

  ImGui::BeginChild("ConsoleScrollArea", ImVec2(0, 0), false, ImGuiWindowFlags_HorizontalScrollbar);

  std::vector<CM_LogLine> lines = CM_LogBuffer::Get().GetLines();
  for (const CM_LogLine& line : lines) {
    if (m_filter[0] != '\0' && line.text.find(m_filter) == std::string::npos) {
      continue;
    }
    ImGui::PushStyleColor(ImGuiCol_Text, GetLevelColor(line.level));
    ImGui::TextUnformatted(line.text.c_str());
    ImGui::PopStyleColor();
  }

  if (m_autoScroll && ImGui::GetScrollY() >= ImGui::GetScrollMaxY()) {
    ImGui::SetScrollHereY(1.0f);
  }

  ImGui::EndChild();
  ImGui::End();
}
