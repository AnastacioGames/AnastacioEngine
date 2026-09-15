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
 * Contributor(s): Range Engine
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_InputSystem.h
 *  \ingroup ketsji
 */

#ifndef __KX_INPUTSYSTEM_H__
#define __KX_INPUTSYSTEM_H__

#include <vector>
#include <string>

#include "EXP_PyObjectPlus.h"
#include "KX_InputTable.h"

#include "SCA_IInputDevice.h"

#include <filesystem> // C++17

namespace fs = std::filesystem;

class KX_InputSystem : public EXP_PyObjectPlus
{
	Py_Header
private:
	class SCA_IInputDevice *m_inputDevice;

	std::string m_path; // InputSystem folder path (ex: "GameProject"/KeyMapping)

	// We're going to store a vector containing all the inputTables of each inputMap,
	// this way is better than create a new EXP_VALUE for inputMaps because it gives quick access to values ​​in python.
	// const char is the name of the inputTable.
	std::vector<std::pair<std::string, std::vector<KX_InputTable *>>> m_inputTables;

public:
	KX_InputSystem(class SCA_IInputDevice *keyboard);
	virtual ~KX_InputSystem();

	void ClearInputTables();
	void LoadInputMaps();
	std::string OpenInputMap(fs::path file_path, const char *inputMap_name);

#ifdef WITH_PYTHON
	EXP_PYMETHOD_DOC(KX_InputSystem, changeKeyMap);
	EXP_PYMETHOD_DOC(KX_InputSystem, changeSensitivity);
	EXP_PYMETHOD_DOC(KX_InputSystem, changeJoystickIndex);
	EXP_PYMETHOD_NOARGS(KX_InputSystem, ReloadInputMaps);

	static PyObject*	pyattr_get_input_maps(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
#endif
};

#endif  /* __KX_INPUTSYSTEM_H__ */
