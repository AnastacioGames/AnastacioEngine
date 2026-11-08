/*******************************************************************************
 * Anastacio Engine: aud.voice_fx, aud.edit, aud.peak.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/

#include "PyVoiceFX.h"
#include "PySound.h"

#include "Exception.h"
#include "fx/VoiceFX.h"

#include <memory>

using namespace aud;

extern PyObject* AUDError;

namespace {

std::shared_ptr<ISound> soundOf(PyObject* object)
{
	Sound* sound = checkSound(object);
	if(!sound)
		return nullptr;
	return *reinterpret_cast<std::shared_ptr<ISound>*>(sound->sound);
}

PyObject* wrap(std::shared_ptr<ISound> sound)
{
	Sound* result = (Sound*)Sound_empty();
	if(result)
		result->sound = new std::shared_ptr<ISound>(sound);
	return (PyObject*)result;
}

}

PyDoc_STRVAR(M_aud_voice_fx_doc,
			 ".. function:: voice_fx(sound, preset, amount=1.0)\n\n"
			 "   Applies a voice preset: NONE, CHIPMUNK, GIANT, ROBOT, RADIO, ECHO, CAVE, REVERSE.\n"
			 "   amount goes from 0 (dry) to 1 (full effect). REVERSE needs a recorded sound.\n\n"
			 "   :rtype: :class:`Sound`");

static PyObject* aud_voice_fx(PyObject*, PyObject* args, PyObject* kwds)
{
	static const char* kwlist[] = {"sound", "preset", "amount", nullptr};
	PyObject* object;
	const char* preset;
	float amount = 1.0f;
	if(!PyArg_ParseTupleAndKeywords(args, kwds, "Os|f:voice_fx", const_cast<char**>(kwlist), &object, &preset, &amount))
		return nullptr;
	std::shared_ptr<ISound> sound = soundOf(object);
	if(!sound)
		return nullptr;
	try
	{
		return wrap(VoiceFX::apply(sound, preset, amount));
	}
	catch(Exception& e)
	{
		PyErr_SetString(AUDError, e.what());
		return nullptr;
	}
}

PyDoc_STRVAR(M_aud_edit_doc,
			 ".. function:: edit(sound, start=0.0, end=-1.0, fade_in=0.0, fade_out=0.0, normalize=False)\n\n"
			 "   Non-destructive cut, fades and peak normalization (end < 0 = until the end).\n\n"
			 "   :rtype: :class:`Sound`");

static PyObject* aud_edit(PyObject*, PyObject* args, PyObject* kwds)
{
	static const char* kwlist[] = {"sound", "start", "end", "fade_in", "fade_out", "normalize", nullptr};
	PyObject* object;
	float start = 0.0f, end = -1.0f, fade_in = 0.0f, fade_out = 0.0f;
	int normalize = 0;
	if(!PyArg_ParseTupleAndKeywords(args, kwds, "O|ffffp:edit", const_cast<char**>(kwlist), &object, &start, &end,
	                                &fade_in, &fade_out, &normalize))
		return nullptr;
	std::shared_ptr<ISound> sound = soundOf(object);
	if(!sound)
		return nullptr;
	try
	{
		return wrap(VoiceFX::edit(sound, start, end, fade_in, fade_out, normalize != 0));
	}
	catch(Exception& e)
	{
		PyErr_SetString(AUDError, e.what());
		return nullptr;
	}
}

PyDoc_STRVAR(M_aud_peak_doc,
			 ".. function:: peak(sound, max_seconds=600.0)\n\n"
			 "   Largest absolute sample of the sound (0..1 for normal audio).\n\n"
			 "   :rtype: float");

static PyObject* aud_peak(PyObject*, PyObject* args, PyObject* kwds)
{
	static const char* kwlist[] = {"sound", "max_seconds", nullptr};
	PyObject* object;
	float max_seconds = 600.0f;
	if(!PyArg_ParseTupleAndKeywords(args, kwds, "O|f:peak", const_cast<char**>(kwlist), &object, &max_seconds))
		return nullptr;
	std::shared_ptr<ISound> sound = soundOf(object);
	if(!sound)
		return nullptr;
	try
	{
		float value;
		Py_BEGIN_ALLOW_THREADS
		value = VoiceFX::peak(sound, max_seconds);
		Py_END_ALLOW_THREADS
		return PyFloat_FromDouble(value);
	}
	catch(Exception& e)
	{
		PyErr_SetString(AUDError, e.what());
		return nullptr;
	}
}

PyDoc_STRVAR(M_aud_duration_doc,
			 ".. function:: duration(sound)\n\n"
			 "   Length in seconds, or -1 if unknown/infinite.\n\n"
			 "   :rtype: float");

static PyObject* aud_duration(PyObject*, PyObject* object)
{
	std::shared_ptr<ISound> sound = soundOf(object);
	if(!sound)
		return nullptr;
	try
	{
		return PyFloat_FromDouble(VoiceFX::duration(sound));
	}
	catch(Exception& e)
	{
		PyErr_SetString(AUDError, e.what());
		return nullptr;
	}
}

PyDoc_STRVAR(M_aud_voice_presets_doc,
			 ".. function:: voice_presets(live=False)\n\n"
			 "   Preset names for voice_fx. With live=True, leaves out the ones that need a recorded sound.\n\n"
			 "   :rtype: list of str");

static PyObject* aud_voice_presets(PyObject*, PyObject* args, PyObject* kwds)
{
	static const char* kwlist[] = {"live", nullptr};
	int live = 0;
	if(!PyArg_ParseTupleAndKeywords(args, kwds, "|p:voice_presets", const_cast<char**>(kwlist), &live))
		return nullptr;
	PyObject* list = PyList_New(0);
	for(const std::string& name : VoiceFX::presetNames())
	{
		if(live && VoiceFX::needsRecorded(name))
			continue;
		PyObject* item = PyUnicode_FromString(name.c_str());
		PyList_Append(list, item);
		Py_DECREF(item);
	}
	return list;
}

PyDoc_STRVAR(M_aud_save_wav_doc,
			 ".. function:: save_wav(sound, path, max_seconds=600.0)\n\n"
			 "   Writes the sound as 16-bit PCM WAV (works on the Web too, unlike Sound.write).");

static PyObject* aud_save_wav(PyObject*, PyObject* args, PyObject* kwds)
{
	static const char* kwlist[] = {"sound", "path", "max_seconds", nullptr};
	PyObject* object;
	const char* path;
	float max_seconds = 600.0f;
	if(!PyArg_ParseTupleAndKeywords(args, kwds, "Os|f:save_wav", const_cast<char**>(kwlist), &object, &path, &max_seconds))
		return nullptr;
	std::shared_ptr<ISound> sound = soundOf(object);
	if(!sound)
		return nullptr;
	try
	{
		VoiceFX::saveWAV(sound, path, max_seconds);
	}
	catch(Exception& e)
	{
		PyErr_SetString(AUDError, e.what());
		return nullptr;
	}
	Py_RETURN_NONE;
}

static PyMethodDef voice_fx_methods[] = {
	{"save_wav", (PyCFunction)aud_save_wav, METH_VARARGS | METH_KEYWORDS, M_aud_save_wav_doc},
	{"voice_fx", (PyCFunction)aud_voice_fx, METH_VARARGS | METH_KEYWORDS, M_aud_voice_fx_doc},
	{"edit", (PyCFunction)aud_edit, METH_VARARGS | METH_KEYWORDS, M_aud_edit_doc},
	{"peak", (PyCFunction)aud_peak, METH_VARARGS | METH_KEYWORDS, M_aud_peak_doc},
	{"duration", (PyCFunction)aud_duration, METH_O, M_aud_duration_doc},
	{"voice_presets", (PyCFunction)aud_voice_presets, METH_VARARGS | METH_KEYWORDS, M_aud_voice_presets_doc},
	{nullptr, nullptr, 0, nullptr}
};

void addVoiceFXToModule(PyObject* module)
{
	PyModule_AddFunctions(module, voice_fx_methods);
}
