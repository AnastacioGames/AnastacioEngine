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

 /** \file KXImgui/KX_Imgui.cpp
  *  \ingroup ketsji
  */

extern "C" {
	#include "BKE_appdir.h"

	extern int datatoc_roboto_medium_ttf_size;
	extern char datatoc_roboto_medium_ttf[];

	extern int datatoc_forkawesome_icon_font_ttf_size;
	extern char datatoc_forkawesome_icon_font_ttf[];
}

#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "KX_Scene.h"

#include "KX_Imgui.h"
#include "KX_Imgui_Impl_Inputs.h"

#include "IconsForkAwesome.h"
#include "imgui_impl_opengl3.h"

#include "GPU_glew.h"
#include "GPU_texture.h"

KX_Imgui::KX_Imgui()
	:streamImguiConfig_Write(std::ofstream()),
	streamImguiConfig_Read(std::ifstream()),
	streamImguiConfig_Open(false)
{
}

KX_Imgui::~KX_Imgui()
{
	// Nothing
}

void KX_Imgui::Init(DEV_InputDevice *inputDevice)
{
	IMGUI_CHECKVERSION();
	ImGui::CreateContext();
	ImPlot::CreateContext();
	ImGuiIO& io = ImGui::GetIO();
	io.ConfigDockingWithShift = true;

	// Init
	KX_ImGui_Impl_Inputs_InitForOpenGL(inputDevice, nullptr);
#ifdef __EMSCRIPTEN__
	/* WebGL2/GLES3 does not accept desktop GLSL 120; use the ES3 shader variant. */
	ImGui_ImplOpenGL3_Init("#version 300 es");
#else
	ImGui_ImplOpenGL3_Init("#version 120");
#endif

	// Load imgui.ini file
	imguiConfigPath = std::string(BKE_appdir_program_dir()) + "\\imgui.ini";
	std::ifstream ini_file(imguiConfigPath.c_str());

	if (ini_file.is_open()) {
		std::stringstream ini_stream;
		ini_stream << ini_file.rdbuf();
		std::string ini_string = ini_stream.str();

		// read from memory
		ImGui::LoadIniSettingsFromMemory(ini_string.c_str(), ini_string.size() + 1);

		ini_file.close();
		}

	// Add Blender Font in C to Dear ImGui.
    ImFontConfig font_cfg;
	font_cfg.FontDataOwnedByAtlas = false; // Important to set this to false to prevent ImGui from trying to free memory.
	io.Fonts->AddFontFromMemoryTTF((void*)datatoc_roboto_medium_ttf, (int)datatoc_roboto_medium_ttf_size, 12.0f, &font_cfg);

	/* Kenney Icons */
	ImFontConfig icon_cfg;
	icon_cfg.MergeMode = true;
	icon_cfg.GlyphMinAdvanceX = 12.0f;
	icon_cfg.FontDataOwnedByAtlas = false;
	static const ImWchar icon_ranges[] = { ICON_MIN_FK, ICON_MAX_FK, 0 };
	io.Fonts->AddFontFromMemoryTTF((void*)datatoc_forkawesome_icon_font_ttf, (int)datatoc_forkawesome_icon_font_ttf_size, 12.0f, &icon_cfg, icon_ranges);

	// Setup ImGui style
	SetupDebugModeStyle();

	// Initialize Variables //
	// Docking
	io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
	// Keyboard navigation (Tab/arrows move focus between widgets) -- required for
	// Python-drawn game menus to be usable without a mouse.
	io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
	// Gamepad navigation (D-Pad/face buttons/sticks move focus and activate widgets) --
	// actual button/axis reads happen in KX_Imgui_Impl_Inputs.cpp's ImGui_ImplSDL2_UpdateGamepads().
	io.ConfigFlags |= ImGuiConfigFlags_NavEnableGamepad;
}

void KX_Imgui::NextFrame()
{
	ImGuiIO& io = ImGui::GetIO();
	io.DisplaySize = ImVec2(KX_GetActiveEngine()->GetCanvas()->GetArea().GetWidth(), KX_GetActiveEngine()->GetCanvas()->GetArea().GetHeight());

	ImGui_ImplOpenGL3_NewFrame();
	KX_ImGui_Impl_Inputs_NewFrame();
	ImGui::NewFrame();
}

void KX_Imgui::ProcessInputEvents()
{
	KX_ImGui_Impl_Inputs_ProcessEvent();
}

void KX_Imgui::Render()
{
	DrawCustomCursor();

	ImGui::Render();
	ImVec2 KX_Viewport(KX_GetActiveEngine()->GetCanvas()->GetArea().GetLeft(), KX_GetActiveEngine()->GetCanvas()->GetArea().GetBottom());
	ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData(), KX_Viewport);
}

// TODO: ReWork this
void DrawCustomCursor() {
	KX_KetsjiEngine::CustomMouseCursor *customCursor = KX_GetActiveEngine()->GetCustomMouseCursor();

	if (!customCursor)
		return;

	if (!customCursor->m_visible)
		return;

	intptr_t image_bindCode = (intptr_t)GPU_texture_opengl_bindcode(customCursor->m_tex);

	// GPU_texture_filter_mode() uses target not bindcode, wait Range 2.0 because there is more organized. for now it will use raw OpenGL calls.
	glBindTexture(GL_TEXTURE_2D, image_bindCode);
	if (customCursor->m_mipmap) {
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	}
	else {
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
	}
	glBindTexture(GL_TEXTURE_2D, 0);

	ImGuiIO& io = ImGui::GetIO();
	const int iconSize = customCursor->m_size; // Pixel size

	ImVec2 mousePos = io.MousePos;
	mousePos.x += customCursor->m_offset_X;
	mousePos.y += customCursor->m_offset_Y;

	ImVec2 p2(mousePos.x + iconSize, mousePos.y);
	ImVec2 p3(mousePos.x + iconSize, mousePos.y + iconSize);
	ImVec2 p4(mousePos.x, mousePos.y + iconSize);

	ImGui::GetForegroundDrawList()->AddImageQuad((ImTextureID)image_bindCode, mousePos, p2, p3, p4,
												ImVec2(0, 1), ImVec2(1, 1), ImVec2(1, 0), ImVec2(0, 0));
}

void KX_Imgui::Stop()
{
	ImGui_ImplOpenGL3_Shutdown();
	KX_ImGui_Impl_Inputs_Shutdown();

	std::string finalpath = std::string(BKE_appdir_program_dir()) + "\\imgui.ini";
	ImGui::SaveIniSettingsToDisk(finalpath.c_str());

	ImPlot::DestroyContext();
	ImGui::DestroyContext();

	// Save vars
	//SaveDebugMode();
}

/// Custom Save/Load from imgui.ini

// Save

void KX_Imgui::OpenImgui_Config_ToSave(const char *sectionName)
{
	// Open imgui.ini.
    streamImguiConfig_Write = std::ofstream(imguiConfigPath, std::ios_base::app);

	// Check if imgui.ini is open.
	if (streamImguiConfig_Write.is_open()) {
		// write section name.
		streamImguiConfig_Write << "[" << sectionName << "]" << std::endl;
		streamImguiConfig_Open = true;
	}
	else {
		streamImguiConfig_Open = false;
	}
}

void KX_Imgui::WriteIntValue(const char *name, int intValue) {
	if (streamImguiConfig_Write.is_open())
		streamImguiConfig_Write << name << "=" << intValue << std::endl; // write int value.
}
void KX_Imgui::WriteFloatValue(const char *name, float floatValue) {
	if (streamImguiConfig_Write.is_open())
		streamImguiConfig_Write << name << "=" << floatValue << std::endl; // write float value.
}
void KX_Imgui::WriteBoolValue(const char *name, bool boolValue) {
	if (streamImguiConfig_Write.is_open())
		streamImguiConfig_Write << name << "=" << (boolValue ? "true" : "false") << std::endl; // write bool value.
}
void KX_Imgui::WriteCharValue(const char *name, char charValue) {
	if (streamImguiConfig_Write.is_open())
		streamImguiConfig_Write << name << "=" << charValue << std::endl; // write char value.
}

void KX_Imgui::SaveAndCloseImgui_Config() {
  if (streamImguiConfig_Write.is_open()) {
        streamImguiConfig_Write << std::endl;  // Blank line for separe sections.
        streamImguiConfig_Write.close();       // Close imgui.ini.
    }
}

// Load

void KX_Imgui::OpenImgui_Config_ToLoad()
{
	// Open imgui.ini.
    streamImguiConfig_Read = std::ifstream(imguiConfigPath);

	// Check if imgui.ini is open.
    if (streamImguiConfig_Read.is_open()) {
		streamImguiConfig_Open = true;
	}
	else {
		streamImguiConfig_Open = false;
	}
}

bool KX_Imgui::LoadSection_Config(std::string SectionName)
{
  if (streamImguiConfig_Open) {
        std::string line;
        std::string currentSection;

        bool isInSection = false;

        // Run the file.
        while (std::getline(streamImguiConfig_Read, line)) {
            // Check if have a section..
            if (line.size() > 2 && line.front() == '[' && line.back() == ']') {
                currentSection = line.substr(1, line.size() - 2);
				// Check Section.
                isInSection = (currentSection == SectionName);
            }

            if (isInSection) {
                break;
			}
		}
		if (!isInSection) {

		}
		return isInSection;
    }
	return false;
}

int KX_Imgui::LoadIntValue() {
    std::string line;
	// get line.
    std::getline(streamImguiConfig_Read, line);

	// Check if have a value.
    size_t equalSignPos = line.find('=');
    if (equalSignPos != std::string::npos) {
        std::string value = line.substr(equalSignPos + 1);
		return std::stoi(value);
	}
	// Error!
	printf("Load from imgui.ini: Int value -> Error! \n");
    return 0;
}

float KX_Imgui::LoadFloatValue() {
    std::string line;
	// get line.
    std::getline(streamImguiConfig_Read, line);

	// Check if have a value.
    size_t equalSignPos = line.find('=');
    if (equalSignPos != std::string::npos) {
        std::string value = line.substr(equalSignPos + 1);

        return std::stof(value);
	}
	// Error!
	printf("Load from imgui.ini: Float value -> Error! \n");
    return 0.f;
}

bool KX_Imgui::LoadBoolValue() {
    std::string line;
	// get line.
    std::getline(streamImguiConfig_Read, line);

	// Check if have a value.
    size_t equalSignPos = line.find('=');
    if (equalSignPos != std::string::npos) {
        std::string value = line.substr(equalSignPos + 1);

        return (value == "true") ? true : false;
	}
	// Error!
	printf("Load from imgui.ini: Bool value -> Error! \n");
    return false;
}

std::string KX_Imgui::LoadStringValue() {
    std::string line;
	// get line.
    std::getline(streamImguiConfig_Read, line);

	// Check if have a value.
    size_t equalSignPos = line.find('=');
    if (equalSignPos != std::string::npos) {
        std::string value = line.substr(equalSignPos + 1);

        return value;
	}
	// Error!
	printf("Load from imgui.ini: String value -> Error! \n");
    return "";
}

void KX_Imgui::CloseImgui_Config() {
    streamImguiConfig_Read.close();  // Close the file
    streamImguiConfig_Open = false;
}

/// Style

void SetupDebugModeStyle() {
	ImGuiStyle& style = ImGui::GetStyle();

	style.Alpha = 1.0f;
	style.DisabledAlpha = 0.5f;
	style.WindowPadding = ImVec2(8.0f, 8.0f);
	style.WindowRounding = 5.0f;
	style.WindowBorderSize = 1.0f;
	style.WindowMinSize = ImVec2(20.0f, 20.0f);
	style.WindowTitleAlign = ImVec2(0.0f, 0.5f);
	style.WindowMenuButtonPosition = ImGuiDir_Left;
	style.ChildRounding = 3.5f;
	style.ChildBorderSize = 1.0f;
	style.PopupRounding = 2.0f;
	style.PopupBorderSize = 1.0f;
	style.FramePadding = ImVec2(4.0f, 3.0f);
	style.FrameRounding = 5.0f;
	style.FrameBorderSize = 0.0f;
	style.ItemSpacing = ImVec2(4.0f, 2.099999904632568f);
	style.ItemInnerSpacing = ImVec2(4.0f, 4.0f);
	style.CellPadding = ImVec2(4.0f, 2.0f);
	style.IndentSpacing = 2.0f;
	style.ColumnsMinSpacing = 6.0f;
	style.ScrollbarSize = 14.0f;
	style.ScrollbarRounding = 9.0f;
	style.GrabMinSize = 10.0f;
	style.GrabRounding = 5.0f;
	style.TabRounding = 4.0f;
	style.TabBorderSize = 0.0f;
	style.TabMinWidthForCloseButton = 0.0f;
	style.ColorButtonPosition = ImGuiDir_Right;
	style.ButtonTextAlign = ImVec2(0.5f, 0.5f);
	style.SelectableTextAlign = ImVec2(0.0f, 0.0f);

	style.Colors[ImGuiCol_Text] = ImVec4(1.000f, 1.000f, 1.000f, 1.000f);
	style.Colors[ImGuiCol_TextDisabled] = ImVec4(0.498f, 0.498f, 0.498f, 1.000f);
	style.Colors[ImGuiCol_WindowBg] = ImVec4(0.059f, 0.059f, 0.059f, 0.25f); //
	style.Colors[ImGuiCol_ChildBg] = ImVec4(0.000f, 0.000f, 0.000f, 0.098f);
	style.Colors[ImGuiCol_PopupBg] = ImVec4(0.078f, 0.078f, 0.078f, 0.940f);
	style.Colors[ImGuiCol_Border] = ImVec4(0.427f, 0.427f, 0.498f, 0.502f);
	style.Colors[ImGuiCol_BorderShadow] = ImVec4(0.000f, 0.000f, 0.000f, 0.000f);
	style.Colors[ImGuiCol_FrameBg] = ImVec4(0.200f, 0.208f, 0.220f, 0.541f);
	style.Colors[ImGuiCol_FrameBgHovered] = ImVec4(0.400f, 0.400f, 0.400f, 0.400f);
	style.Colors[ImGuiCol_FrameBgActive] = ImVec4(0.176f, 0.176f, 0.176f, 0.671f);
	style.Colors[ImGuiCol_TitleBg] = ImVec4(0.2f, 0.05f, 0.05f, 1.0f); // Dark and discreet red
	style.Colors[ImGuiCol_TitleBgActive] = ImVec4(0.3f, 0.1f, 0.1f, 1.0f); // A little brighter red, but still soft
	style.Colors[ImGuiCol_TitleBgCollapsed] = ImVec4(0.000f, 0.000f, 0.000f, 0.510f);
	style.Colors[ImGuiCol_MenuBarBg] = ImVec4(0.137f, 0.137f, 0.137f, 0.5f);
	style.Colors[ImGuiCol_ScrollbarBg] = ImVec4(0.020f, 0.020f, 0.020f, 0.530f);
	style.Colors[ImGuiCol_ScrollbarGrab] = ImVec4(0.310f, 0.310f, 0.310f, 1.000f);
	style.Colors[ImGuiCol_ScrollbarGrabHovered] = ImVec4(0.408f, 0.408f, 0.408f, 1.000f);
	style.Colors[ImGuiCol_ScrollbarGrabActive] = ImVec4(0.510f, 0.510f, 0.510f, 1.000f);
	style.Colors[ImGuiCol_CheckMark] = ImVec4(0.937f, 0.937f, 0.937f, 1.000f);
	style.Colors[ImGuiCol_SliderGrab] = ImVec4(0.510f, 0.510f, 0.510f, 1.000f);
	style.Colors[ImGuiCol_SliderGrabActive] = ImVec4(0.859f, 0.859f, 0.859f, 1.000f);
	style.Colors[ImGuiCol_Button] = ImVec4(0.294f, 0.294f, 0.294f, 0.588f);
	style.Colors[ImGuiCol_ButtonHovered] = ImVec4(0.459f, 0.467f, 0.478f, 1.000f);
	style.Colors[ImGuiCol_ButtonActive] = ImVec4(0.420f, 0.420f, 0.420f, 1.000f);
	style.Colors[ImGuiCol_Header] = ImVec4(0.698f, 0.698f, 0.698f, 0.310f);
	style.Colors[ImGuiCol_HeaderHovered] = ImVec4(0.698f, 0.698f, 0.698f, 0.800f);
	style.Colors[ImGuiCol_HeaderActive] = ImVec4(0.478f, 0.498f, 0.518f, 1.000f);
	style.Colors[ImGuiCol_Separator] = ImVec4(0.427f, 0.427f, 0.498f, 0.500f);
	style.Colors[ImGuiCol_SeparatorHovered] = ImVec4(0.718f, 0.718f, 0.718f, 0.780f);
	style.Colors[ImGuiCol_SeparatorActive] = ImVec4(0.510f, 0.510f, 0.510f, 1.000f);
	style.Colors[ImGuiCol_ResizeGrip] = ImVec4(0.910f, 0.910f, 0.910f, 0.250f);
	style.Colors[ImGuiCol_ResizeGripHovered] = ImVec4(0.808f, 0.808f, 0.808f, 0.670f);
	style.Colors[ImGuiCol_ResizeGripActive] = ImVec4(0.459f, 0.459f, 0.459f, 0.950f);
	style.Colors[ImGuiCol_Tab] = ImVec4(0.4f, 0.1f, 0.1f, 0.9f); // Red with slight transparency
	style.Colors[ImGuiCol_TabHovered] = ImVec4(0.6f, 0.2f, 0.2f, 0.8f); // Lighter red for hover
	style.Colors[ImGuiCol_TabActive] = ImVec4(0.5f, 0.15f, 0.15f, 1.0f); // Medium red for active tab
	style.Colors[ImGuiCol_TabUnfocused] = ImVec4(0.2f, 0.1f, 0.1f, 0.8f); //
	style.Colors[ImGuiCol_TabUnfocusedActive] = ImVec4(0.4f, 0.1f, 0.1f, 0.8f); //
	style.Colors[ImGuiCol_PlotLines] = ImVec4(0.608f, 0.608f, 0.608f, 1.000f);
	style.Colors[ImGuiCol_PlotLinesHovered] = ImVec4(1.000f, 0.427f, 0.349f, 1.000f);
	style.Colors[ImGuiCol_PlotHistogram] = ImVec4(0.729f, 0.600f, 0.149f, 1.000f);
	style.Colors[ImGuiCol_PlotHistogramHovered] = ImVec4(1.000f, 0.600f, 0.000f, 1.000f);
	style.Colors[ImGuiCol_TableHeaderBg] = ImVec4(0.188f, 0.188f, 0.200f, 1.000f);
	style.Colors[ImGuiCol_TableBorderStrong] = ImVec4(0.310f, 0.310f, 0.349f, 1.000f);
	style.Colors[ImGuiCol_TableBorderLight] = ImVec4(0.227f, 0.227f, 0.247f, 1.000f);
	style.Colors[ImGuiCol_TableRowBg] = ImVec4(0.000f, 0.000f, 0.000f, 0.000f);
	style.Colors[ImGuiCol_TableRowBgAlt] = ImVec4(1.000f, 1.000f, 1.000f, 0.060f);
	style.Colors[ImGuiCol_TextSelectedBg] = ImVec4(0.867f, 0.867f, 0.867f, 0.350f);
	style.Colors[ImGuiCol_DragDropTarget] = ImVec4(1.000f, 1.000f, 0.000f, 0.900f);
	style.Colors[ImGuiCol_NavHighlight] = ImVec4(0.600f, 0.600f, 0.600f, 1.000f);
	style.Colors[ImGuiCol_NavWindowingHighlight] = ImVec4(1.000f, 1.000f, 1.000f, 0.700f);
	style.Colors[ImGuiCol_NavWindowingDimBg] = ImVec4(0.800f, 0.800f, 0.800f, 0.200f);
	style.Colors[ImGuiCol_ModalWindowDimBg] = ImVec4(0.800f, 0.800f, 0.800f, 0.350f);
}