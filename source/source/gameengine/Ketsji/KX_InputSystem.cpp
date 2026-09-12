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

/** \file gameengine/Ketsji/KX_InputSystem.cpp
 *  \ingroup ketsji
 */

#include "KX_InputSystem.h"

#include "GHOST_C-api.h"
#include "CM_Message.h"

extern "C" {
	#include "BKE_library.h"
	#include "cJSON.h"
}

#include <iostream>
#include <fstream>

/* ------------------------------------------------------------------------- */
/* Native functions                                                          */
/* ------------------------------------------------------------------------- */

KX_InputSystem::KX_InputSystem(SCA_IInputDevice *inputDevice)
	:EXP_PyObjectPlus(),
	m_inputDevice(inputDevice),
	m_inputTables({})
{
	fs::path p = BKE_main_blendfile_path_from_global();
	p.remove_filename(); // There must be a simpler way to get the filepath but I forgot
	p /= "KeyMapping";

	// Store path
	m_path = p.string();

	LoadInputMaps();
}

KX_InputSystem::~KX_InputSystem()
{
}

void KX_InputSystem::ClearInputTables()
{
  for (std::pair<std::string, std::vector<KX_InputTable *>> &pair : m_inputTables) {
    for (KX_InputTable *table : pair.second) {
      delete table;
    }
    pair.second.clear();
  }
  m_inputTables.clear();
}

void KX_InputSystem::LoadInputMaps()
{
	// Free InputTables
	ClearInputTables();

	// Get json files
    if (fs::exists(m_path) && fs::is_directory(m_path)) {
        for (const auto& entry : fs::directory_iterator(m_path)) {
            if (entry.path().extension() == ".json") {

				// Open inputMap.json
                std::ifstream file(entry.path());
                if (file.is_open()) {
                    std::string inputMap((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
                    file.close();

					std::string filename = entry.path().stem().string();

					cJSON *json = cJSON_Parse(inputMap.c_str());
					
					std::vector<KX_InputTable *> inputTables;

					cJSON *inputTable = nullptr;
					cJSON_ArrayForEach(inputTable, json) {
						// Get Values
						cJSON *type = cJSON_GetObjectItem(inputTable, "Type");
						cJSON *controlType = cJSON_GetObjectItem(inputTable, "ControlType");
						cJSON *bindings = cJSON_GetObjectItem(inputTable, "Bindings");
						cJSON *processors = cJSON_GetObjectItem(inputTable, "Processors");

						// check if the value ​​are OK
						if (!type || !controlType || !bindings || !processors) {
							CM_Error("InputSystem " << "'" << filename.c_str() << "' not initialized correctly!");
							break;
						}

						// Create InputTable
						KX_InputTable *KX_inputTable = new KX_InputTable(inputTable->string, 
							type->valuestring, controlType->valuestring, bindings, processors, m_inputDevice);

						// Add InputTable to inputTables
						inputTables.push_back(KX_inputTable);
					}

					// Add InputTable
					m_inputTables.push_back(std::make_pair(filename, inputTables));
					
					// Free allocated json file
					cJSON_Delete(json);
				}
			}
		}
    }
}

std::string KX_InputSystem::OpenInputMap(fs::path file_path, const char *inputMap_name) {
    if (fs::exists(file_path) && fs::is_regular_file(file_path)) {
        std::ifstream file(file_path);
        if (file.is_open()) {
            std::string inputMap((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
            file.close();

            return inputMap;
        }
    }
    
    return "";
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python functions                                                          */
/* ------------------------------------------------------------------------- */

/* Integration hooks ------------------------------------------------------- */
PyTypeObject KX_InputSystem::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_InputSystem",
	sizeof(EXP_PyObjectPlus_Proxy),
	0,
	py_base_dealloc,
	0,
	0,
	0,
	0,
	py_base_repr,
	0, 0, 0, 0, 0, 0, 0, 0, 0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	0, 0, 0, 0, 0, 0, 0,
	Methods,
	0,
	0,
	&EXP_PyObjectPlus::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_InputSystem::Methods[] = {
	{"reloadInputMaps", (PyCFunction)KX_InputSystem::sPyReloadInputMaps, METH_NOARGS},

	EXP_PYMETHODTABLE_KEYWORDS(KX_InputSystem, changeKeyMap),
	EXP_PYMETHODTABLE_KEYWORDS(KX_InputSystem, changeSensitivity),
	EXP_PYMETHODTABLE_KEYWORDS(KX_InputSystem, changeJoystickIndex),
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_InputSystem::Attributes[] = {
    EXP_PYATTRIBUTE_RO_FUNCTION("inputMaps", KX_InputSystem, pyattr_get_input_maps),
	EXP_PYATTRIBUTE_NULL    //Sentinel
};

PyObject *KX_InputSystem::PyReloadInputMaps()
{
  LoadInputMaps();
  CM_Warning("Input maps loaded! Reload input maps is slow, it is discouraged to call this multiple times");

  Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_InputSystem, changeKeyMap,
                    "changeKeyMap(inputMap, inputTable, type, name, keyType, value) \n"
                    "Change the bind key in the input system\n")
{
	const char *inputMap_name;
	const char *inputTable_name;
	const char *name;
	const char *keyType;
	int value = 0;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "ssssi:changeKeyMap", 
									   {"inputMap", "inputTable", "name", "keyType", "value", nullptr},
	                                   &inputMap_name, &inputTable_name, &name, &keyType, &value)) {
		return nullptr;
	}

	fs::path file_path = fs::path(m_path) / (std::string(inputMap_name) + ".json");
	std::string inputMap = OpenInputMap(file_path, inputMap_name);

	cJSON *json = cJSON_Parse(inputMap.c_str());

	cJSON *inputTable = cJSON_GetObjectItem(json, inputTable_name);

	if (inputTable) {
		cJSON *table = cJSON_GetObjectItem(inputTable, "Bindings");

		if (table) {
			cJSON *bind = cJSON_GetObjectItem(table, name);

			cJSON *input;
			cJSON_ArrayForEach(input, bind) {
				// Find the bind type automatically, when found change the keymap and break the loop.
				bool pass = (strcmp(input->string, "COMPOSITEPADS") == 0) ? true :
							(strcmp(input->string, "COMPOSITEPADS3D") == 0) ? true :
							(strcmp(input->string, "BINDING") == 0) ? true : false;

				if (pass) {
					cJSON *key = cJSON_GetObjectItem(input, keyType);

					if (key) {
						cJSON_SetValuestring(key, std::to_string(value).c_str());

						// Save .json back
						char *outputMap = cJSON_Print(json);

						std::filesystem::path outputPath = file_path;

						std::ofstream outputFile(outputPath);
						if (!outputFile.is_open()) {
							CM_Error("Input System, Error opening file for writing!");
										
							// Free
							cJSON_Delete(json);
							free(outputMap);

							Py_RETURN_FALSE;
						}

						// Save OK
						outputFile << outputMap;
						outputFile.close();

						// Free
						cJSON_Delete(json);
						free(outputMap);

						Py_RETURN_TRUE;
					}
				}
			}
		}
	}

	/* Failed */
    CM_Error("Input System, Failed to change Keymap!");

	Py_RETURN_FALSE;
}

EXP_PYMETHODDEF_DOC(KX_InputSystem, changeSensitivity,
                    "changeSensitivity(inputMap, inputTable, name, value) \n"
                    "Change the bind sensitivity in the input system\n")
{
	const char *inputMap_name;
	const char *inputTable_name;
	const char *name;
	float value = 0;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "sssf:changeSensitivity", 
									   {"inputMap", "inputTable", "name", "value", nullptr},
	                                   &inputMap_name, &inputTable_name, &name, &value)) {
		return nullptr;
	}

	fs::path file_path = fs::path(m_path) / (std::string(inputMap_name) + ".json");
	std::string inputMap = OpenInputMap(file_path, inputMap_name);

	cJSON *json = cJSON_Parse(inputMap.c_str());

	cJSON *inputTable = cJSON_GetObjectItem(json, inputTable_name);

	if (inputTable) {
		cJSON *table = cJSON_GetObjectItem(inputTable, "Bindings");

		if (table) {
			cJSON *bind = cJSON_GetObjectItem(table, name);

			cJSON *input;
			cJSON_ArrayForEach(input, bind) {
				// Find the bind type automatically, when found change the keymap and break the loop.
				bool pass = (strcmp(input->string, "PERIPHERALTYPE") == 0);

				if (pass) {
					cJSON *key = cJSON_GetObjectItem(input, "SENSITIVITY");

					if (key) {
						cJSON_SetNumberValue(key, value);

						// Save .json back
						char *outputMap = cJSON_Print(json);

						std::filesystem::path outputPath = file_path;

						std::ofstream outputFile(outputPath);
						if (!outputFile.is_open()) {
							CM_Error("Input System, Error opening file for writing!");
										
							// Free
							cJSON_Delete(json);
							free(outputMap);

							Py_RETURN_FALSE;
						}

						// Save OK
						outputFile << outputMap;
						outputFile.close();

						// Free
						cJSON_Delete(json);
						free(outputMap);

						Py_RETURN_TRUE;
					}
				}
			}
		}
	}

	/* Failed */
	CM_Error("Input System, Failed to change Sensitivity!");

	Py_RETURN_FALSE;
}

EXP_PYMETHODDEF_DOC(KX_InputSystem, changeJoystickIndex,
                    "changeJoystickIndex(inputMap, inputTable, name, value) \n"
                    "Change joystick index in the input system\n")
{
	const char *inputMap_name;
	const char *inputTable_name;
	const char *name;
	int value = 0;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "sssi:changeJoystickIndex", 
									   {"inputMap", "inputTable", "name", "value", nullptr},
	                                   &inputMap_name, &inputTable_name, &name, &value)) {
		return nullptr;
	}

	fs::path file_path = fs::path(m_path) / (std::string(inputMap_name) + ".json");
	std::string inputMap = OpenInputMap(file_path, inputMap_name);

	cJSON *json = cJSON_Parse(inputMap.c_str());

	cJSON *inputTable = cJSON_GetObjectItem(json, inputTable_name);

	if (inputTable) {
		cJSON *table = cJSON_GetObjectItem(inputTable, "Bindings");

		if (table) {
			cJSON *bind = cJSON_GetObjectItem(table, name);

			cJSON *input;
			cJSON_ArrayForEach(input, bind) {
				// Find the bind type automatically, when found change the keymap and break the loop.
				bool pass = (strcmp(input->string, "PERIPHERALTYPE") == 0);

				if (pass) {
					cJSON *key = cJSON_GetObjectItem(input, "INDEX");

					if (key) {
						cJSON_SetIntValue(key, value);

						// Save .json back
						char *outputMap = cJSON_Print(json);

						std::filesystem::path outputPath = file_path;

						std::ofstream outputFile(outputPath);
						if (!outputFile.is_open()) {
							CM_Error("Input System, Error opening file for writing!");
										
							// Free
							cJSON_Delete(json);
							free(outputMap);

							Py_RETURN_FALSE;
						}

						// Save OK
						outputFile << outputMap;
						outputFile.close();

						// Free
						cJSON_Delete(json);
						free(outputMap);

						Py_RETURN_TRUE;
					}
				}
			}
		}
	}

	/* Failed */
	CM_Error("Input System, Failed to change index!");

	Py_RETURN_FALSE;
}

PyObject *KX_InputSystem::pyattr_get_input_maps(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_InputSystem *self = static_cast<KX_InputSystem *>(self_v);

	PyObject *dict = PyDict_New();

	for (std::pair<std::string, std::vector<KX_InputTable *>> inputMap : self->m_inputTables)
	{
		PyObject *key = PyUnicode_FromString(inputMap.first.c_str());

		PyObject *table_dict = PyDict_New();

		for (KX_InputTable *inputTable : inputMap.second) {
			PyObject *table_key = PyUnicode_FromString(inputTable->m_name);

			PyDict_SetItem(table_dict, table_key, inputTable->GetProxy());

			Py_DECREF(table_key);
		}

		PyDict_SetItem(dict, key, table_dict);

		Py_DECREF(key);
		Py_DECREF(table_dict);
	}

	return dict;
}

#endif
