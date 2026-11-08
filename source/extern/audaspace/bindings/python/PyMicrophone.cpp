/*******************************************************************************
 * Anastacio Engine: aud.Microphone.
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

#include "PyMicrophone.h"
#include "PySound.h"

#include "Exception.h"
#include "ISound.h"
#include "devices/Microphone.h"

#include <memory>

extern PyObject* AUDError;

using aud::Microphone;

typedef std::shared_ptr<Microphone> MicPtr;

static Microphone* mic(MicrophoneP* self)
{
	return reinterpret_cast<MicPtr*>(self->microphone)->get();
}

static PyObject* sound_to_python(std::shared_ptr<aud::ISound> sound)
{
	if(!sound)
		Py_RETURN_NONE;

	Sound* obj = (Sound*)Sound_empty();
	if(obj)
		obj->sound = new std::shared_ptr<aud::ISound>(sound);
	return (PyObject*)obj;
}

static PyObject* string_list(const std::vector<std::string>& names)
{
	PyObject* list = PyList_New(names.size());
	for(size_t i = 0; i < names.size(); i++)
		PyList_SET_ITEM(list, i, PyUnicode_FromString(names[i].c_str()));
	return list;
}

static PyObject* Microphone_new(PyTypeObject* type, PyObject* args, PyObject* kwds)
{
	const char* device = nullptr;
	const char* backend = nullptr;
	double rate = aud::RATE_22050;
	int channels = aud::CHANNELS_MONO;
	float seconds = 2.0f;

	static const char* kwlist[] = {"device", "rate", "channels", "backend", "seconds", nullptr};
	if(!PyArg_ParseTupleAndKeywords(args, kwds, "|zdizf:Microphone", const_cast<char**>(kwlist),
	                                &device, &rate, &channels, &backend, &seconds))
		return nullptr;

	if(channels != 1 && channels != 2)
	{
		PyErr_SetString(PyExc_ValueError, "channels must be 1 or 2");
		return nullptr;
	}
	if(rate <= 0)
	{
		PyErr_SetString(PyExc_ValueError, "rate must be positive");
		return nullptr;
	}

	MicrophoneP* self = (MicrophoneP*)type->tp_alloc(type, 0);
	if(self == nullptr)
		return nullptr;

	aud::Specs specs;
	specs.rate = rate;
	specs.channels = aud::Channels(channels);

	try
	{
		self->microphone = new MicPtr(std::make_shared<Microphone>(device ? device : "", specs,
		                                                            backend ? backend : "", seconds));
	}
	catch(aud::Exception& e)
	{
		Py_DECREF(self);
		PyErr_SetString(AUDError, e.what());
		return nullptr;
	}

	return (PyObject*)self;
}

static void Microphone_dealloc(MicrophoneP* self)
{
	if(self->microphone)
		delete reinterpret_cast<MicPtr*>(self->microphone);
	Py_TYPE(self)->tp_free((PyObject*)self);
}

// --- metodos ---------------------------------------------------------------

PyDoc_STRVAR(M_aud_Microphone_start_doc,
	".. method:: start()\n\n"
	"   Opens the capture. Returns False on error (see :attr:`error`).\n"
	"   On the Web it returns True while the permission is still pending.\n\n"
	"   :rtype: bool");

static PyObject* Microphone_start(MicrophoneP* self)
{
	return PyBool_FromLong(mic(self)->start());
}

PyDoc_STRVAR(M_aud_Microphone_stop_doc,
	".. method:: stop()\n\n"
	"   Closes the capture.");

static PyObject* Microphone_stop(MicrophoneP* self)
{
	mic(self)->stop();
	Py_RETURN_NONE;
}

PyDoc_STRVAR(M_aud_Microphone_poll_doc,
	".. method:: poll()\n\n"
	"   Pulls new samples, updating :attr:`level`, :attr:`peak` and the recording.\n"
	"   Call it once per frame/timer tick. Live sounds also poll by themselves.");

static PyObject* Microphone_poll(MicrophoneP* self)
{
	mic(self)->poll();
	Py_RETURN_NONE;
}

PyDoc_STRVAR(M_aud_Microphone_record_start_doc,
	".. method:: record_start()\n\n"
	"   Starts recording from now on.");

static PyObject* Microphone_record_start(MicrophoneP* self)
{
	mic(self)->startRecording();
	Py_RETURN_NONE;
}

PyDoc_STRVAR(M_aud_Microphone_record_stop_doc,
	".. method:: record_stop()\n\n"
	"   Stops recording and returns what was recorded.\n\n"
	"   :rtype: :class:`Sound`");

static PyObject* Microphone_record_stop(MicrophoneP* self)
{
	try
	{
		return sound_to_python(mic(self)->stopRecording());
	}
	catch(aud::Exception& e)
	{
		PyErr_SetString(AUDError, e.what());
		return nullptr;
	}
}

PyDoc_STRVAR(M_aud_Microphone_save_wav_doc,
	".. method:: save_wav(path)\n\n"
	"   Saves the last recording as a 16 bit WAV file.\n\n"
	"   :arg path: File path.\n"
	"   :type path: str");

static PyObject* Microphone_save_wav(MicrophoneP* self, PyObject* args)
{
	const char* path = nullptr;
	if(!PyArg_ParseTuple(args, "s:save_wav", &path))
		return nullptr;

	try
	{
		mic(self)->saveWAV(path);
	}
	catch(aud::Exception& e)
	{
		PyErr_SetString(AUDError, e.what());
		return nullptr;
	}
	Py_RETURN_NONE;
}

PyDoc_STRVAR(M_aud_Microphone_devices_doc,
	".. classmethod:: devices(backend=None)\n\n"
	"   Lists the capture devices of a backend (default: the best one).\n\n"
	"   :rtype: list of str");

static PyObject* Microphone_devices(PyTypeObject*, PyObject* args)
{
	const char* backend = nullptr;
	if(!PyArg_ParseTuple(args, "|z:devices", &backend))
		return nullptr;
	return string_list(Microphone::getDeviceNames(backend ? backend : ""));
}

PyDoc_STRVAR(M_aud_Microphone_backends_doc,
	".. classmethod:: backends()\n\n"
	"   Lists the capture backends (\"OpenAL\", \"WebAudio\", \"Test\").\n\n"
	"   :rtype: list of str");

static PyObject* Microphone_backends(PyTypeObject*)
{
	return string_list(Microphone::getBackendNames());
}

static PyMethodDef Microphone_methods[] = {
	{"start", (PyCFunction)Microphone_start, METH_NOARGS, M_aud_Microphone_start_doc},
	{"stop", (PyCFunction)Microphone_stop, METH_NOARGS, M_aud_Microphone_stop_doc},
	{"poll", (PyCFunction)Microphone_poll, METH_NOARGS, M_aud_Microphone_poll_doc},
	{"record_start", (PyCFunction)Microphone_record_start, METH_NOARGS, M_aud_Microphone_record_start_doc},
	{"record_stop", (PyCFunction)Microphone_record_stop, METH_NOARGS, M_aud_Microphone_record_stop_doc},
	{"save_wav", (PyCFunction)Microphone_save_wav, METH_VARARGS, M_aud_Microphone_save_wav_doc},
	{"devices", (PyCFunction)Microphone_devices, METH_VARARGS | METH_CLASS, M_aud_Microphone_devices_doc},
	{"backends", (PyCFunction)Microphone_backends, METH_NOARGS | METH_CLASS, M_aud_Microphone_backends_doc},
	{nullptr}
};

// --- propriedades ----------------------------------------------------------

static const char* state_name(aud::MicrophoneState state)
{
	switch(state)
	{
	case aud::MICROPHONE_STATE_PENDING: return "pending";
	case aud::MICROPHONE_STATE_GRANTED: return "granted";
	case aud::MICROPHONE_STATE_DENIED:  return "denied";
	case aud::MICROPHONE_STATE_ERROR:   return "error";
	default:                            return "closed";
	}
}

static PyObject* Microphone_get_state(MicrophoneP* self, void*)
{
	return PyUnicode_FromString(state_name(mic(self)->getState()));
}

static PyObject* Microphone_get_error(MicrophoneP* self, void*)
{
	return PyUnicode_FromString(mic(self)->getError().c_str());
}

static PyObject* Microphone_get_backend(MicrophoneP* self, void*)
{
	return PyUnicode_FromString(mic(self)->getBackendName().c_str());
}

static PyObject* Microphone_get_active(MicrophoneP* self, void*)
{
	return PyBool_FromLong(mic(self)->isActive());
}

static PyObject* Microphone_get_level(MicrophoneP* self, void*)
{
	return PyFloat_FromDouble(mic(self)->getLevel());
}

static PyObject* Microphone_get_peak(MicrophoneP* self, void*)
{
	return PyFloat_FromDouble(mic(self)->getPeak());
}

static PyObject* Microphone_get_dropped(MicrophoneP* self, void*)
{
	return PyLong_FromLong(mic(self)->getDropped());
}

static PyObject* Microphone_get_rate(MicrophoneP* self, void*)
{
	return PyFloat_FromDouble(mic(self)->getSpecs().rate);
}

static PyObject* Microphone_get_channels(MicrophoneP* self, void*)
{
	return PyLong_FromLong(mic(self)->getSpecs().channels);
}

static PyObject* Microphone_get_recording(MicrophoneP* self, void*)
{
	return PyBool_FromLong(mic(self)->isRecording());
}

static PyObject* Microphone_get_recording_seconds(MicrophoneP* self, void*)
{
	return PyFloat_FromDouble(mic(self)->getRecordingSeconds());
}

static PyObject* Microphone_get_last_recording(MicrophoneP* self, void*)
{
	return sound_to_python(mic(self)->getLastRecording());
}

static PyObject* Microphone_get_live(MicrophoneP* self, void*)
{
	return sound_to_python(mic(self)->createLiveSound());
}

static PyGetSetDef Microphone_properties[] = {
	{(char*)"state", (getter)Microphone_get_state, nullptr,
	 (char*)"'closed', 'pending', 'granted', 'denied' or 'error'.", nullptr},
	{(char*)"error", (getter)Microphone_get_error, nullptr, (char*)"Last error message.", nullptr},
	{(char*)"backend", (getter)Microphone_get_backend, nullptr, (char*)"Backend in use.", nullptr},
	{(char*)"active", (getter)Microphone_get_active, nullptr, (char*)"Whether the capture is open.", nullptr},
	{(char*)"level", (getter)Microphone_get_level, nullptr, (char*)"RMS level of the last block (0..1).", nullptr},
	{(char*)"peak", (getter)Microphone_get_peak, nullptr, (char*)"Peak level with smooth fall (0..1).", nullptr},
	{(char*)"dropped", (getter)Microphone_get_dropped, nullptr, (char*)"How many times samples were lost.", nullptr},
	{(char*)"rate", (getter)Microphone_get_rate, nullptr, (char*)"Real sample rate.", nullptr},
	{(char*)"channels", (getter)Microphone_get_channels, nullptr, (char*)"Channel count.", nullptr},
	{(char*)"recording", (getter)Microphone_get_recording, nullptr, (char*)"Whether it is recording.", nullptr},
	{(char*)"recording_seconds", (getter)Microphone_get_recording_seconds, nullptr,
	 (char*)"Length of the current recording.", nullptr},
	{(char*)"last_recording", (getter)Microphone_get_last_recording, nullptr,
	 (char*)"Last recording as a Sound, or None.", nullptr},
	{(char*)"live", (getter)Microphone_get_live, nullptr,
	 (char*)"A new Sound that plays the microphone live (silence when there is no data).", nullptr},
	{nullptr}
};

PyDoc_STRVAR(M_aud_Microphone_doc,
	"Microphone(device=None, rate=22050, channels=1, backend=None, seconds=2.0)\n\n"
	"Microphone capture. Default is light voice quality: mono, 22050 Hz.\n\n"
	"   mic = aud.Microphone()\n"
	"   mic.start()\n"
	"   mic.poll(); print(mic.level)\n"
	"   mic.record_start(); ...; sound = mic.record_stop()\n"
	"   mic.save_wav('voice.wav')\n"
	"   aud.Device().play(mic.live.pitch(1.5))\n");

PyTypeObject MicrophoneType = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"aud.Microphone",                  /* tp_name */
	sizeof(MicrophoneP),               /* tp_basicsize */
	0,                                 /* tp_itemsize */
	(destructor)Microphone_dealloc,    /* tp_dealloc */
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	Py_TPFLAGS_DEFAULT,                /* tp_flags */
	M_aud_Microphone_doc,              /* tp_doc */
	0, 0, 0, 0, 0, 0,
	Microphone_methods,                /* tp_methods */
	0,                                 /* tp_members */
	Microphone_properties,             /* tp_getset */
	0, 0, 0, 0, 0, 0, 0,
	Microphone_new,                    /* tp_new */
};

AUD_API MicrophoneP* checkMicrophone(PyObject* microphone)
{
	if(!PyObject_TypeCheck(microphone, &MicrophoneType))
	{
		PyErr_SetString(PyExc_TypeError, "Object is not of type Microphone!");
		return nullptr;
	}
	return (MicrophoneP*)microphone;
}

AUD_API void* Microphone_getSharedPointer(PyObject* microphone)
{
	MicrophoneP* self = checkMicrophone(microphone);
	return self ? self->microphone : nullptr;
}

AUD_API PyObject* Microphone_fromSharedPointer(void* shared_pointer)
{
	MicrophoneP* self = (MicrophoneP*)MicrophoneType.tp_alloc(&MicrophoneType, 0);
	if(self)
		self->microphone = new MicPtr(*reinterpret_cast<MicPtr*>(shared_pointer));
	return (PyObject*)self;
}

bool initializeMicrophone()
{
	return PyType_Ready(&MicrophoneType) >= 0;
}

void addMicrophoneToModule(PyObject* module)
{
	Py_INCREF(&MicrophoneType);
	PyModule_AddObject(module, "Microphone", (PyObject*)&MicrophoneType);
}
