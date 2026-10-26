/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Ketsji/KX_TrackLine.cpp
 *  \ingroup ketsji
 *
 * Range.types.TrackLine: closed polyline for racing AI (progress along the track, point and
 * side at a distance, per-vertex profiles such as curvature or safe speed). Same math as the
 * Python version it replaces, without the per-call interpreter cost.
 */

#ifdef WITH_PYTHON

#include "KX_TrackLine.h"
#include "KX_PyMath.h"

#include <algorithm>
#include <cmath>
#include <map>
#include <string>
#include <string_view>
#include <vector>

namespace {

struct Vec3d {
	double x, y, z;
};

struct TrackLineData {
	std::vector<Vec3d> points;
	std::vector<double> cum;
	double length;
	std::map<std::string, std::vector<double>, std::less<>> profiles;
};

struct KX_TrackLineObject {
	PyObject_HEAD
	TrackLineData *data;
};

bool ReadVec3(PyObject *item, Vec3d &out)
{
	mt::vec3 v;
	if (!PyVecTo(item, v)) {
		return false;
	}
	out = {v.x, v.y, v.z};
	return true;
}

PyObject *MakeVector(const Vec3d &v)
{
	return PyObjectFrom(mt::vec3((float)v.x, (float)v.y, (float)v.z));
}

/* Python modulo (non-negative for a positive divisor). */
double WrapS(double s, double length)
{
	double r = std::fmod(s, length);
	if (r < 0.0) {
		r += length;
	}
	return r;
}

/* Segment index for s (already wrapped), same as bisect_right(cum, s) - 1, and t inside it. */
int SegmentAt(const TrackLineData &d, double s, double &t)
{
	const int i = std::max(0, int(std::upper_bound(d.cum.begin(), d.cum.end(), s) - d.cum.begin()) - 1);
	const double segEnd = (i + 1 < (int)d.cum.size()) ? d.cum[i + 1] : d.length;
	const double seg = segEnd - d.cum[i];
	t = (seg <= 0.0) ? 0.0 : (s - d.cum[i]) / seg;
	return i;
}

Vec3d PointAt(const TrackLineData &d, double s)
{
	double t;
	const int n = (int)d.points.size();
	const int i = SegmentAt(d, WrapS(s, d.length), t);
	const Vec3d &a = d.points[i];
	const Vec3d &b = d.points[(i + 1) % n];
	return {a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t};
}

/* Projection of pos on segment i: squared distance and s along the line. */
void Project(const TrackLineData &d, const Vec3d &pos, int i, double &d2, double &s)
{
	const int n = (int)d.points.size();
	const Vec3d &a = d.points[i];
	const Vec3d &b = d.points[(i + 1) % n];
	const double abx = b.x - a.x, aby = b.y - a.y, abz = b.z - a.z;
	const double l2 = abx * abx + aby * aby + abz * abz;
	double t = 0.0;
	if (l2 != 0.0) {
		t = ((pos.x - a.x) * abx + (pos.y - a.y) * aby + (pos.z - a.z) * abz) / l2;
		t = std::max(0.0, std::min(1.0, t));
	}
	const double px = pos.x - (a.x + abx * t), py = pos.y - (a.y + aby * t), pz = pos.z - (a.z + abz * t);
	d2 = px * px + py * py + pz * pz;
	s = d.cum[i] + t * std::sqrt(l2);
}

/* Every segment is tested: the nearest vertex is not always on the nearest segment
 * (uneven point spacing), so a vertex-first search could pick a segment meters away. */
void LocateGlobal(const TrackLineData &d, const Vec3d &pos, double &bestD2, double &bestS, int &bestI)
{
	const int n = (int)d.points.size();
	bestI = -1;
	for (int i = 0; i < n; i++) {
		double d2, s;
		Project(d, pos, i, d2, s);
		if (bestI < 0 || d2 < bestD2) {
			bestD2 = d2;
			bestS = s;
			bestI = i;
		}
	}
}

void TrackLine_dealloc(KX_TrackLineObject *self)
{
	delete self->data;
	Py_TYPE(self)->tp_free((PyObject *)self);
}

int TrackLine_init(KX_TrackLineObject *self, PyObject *args, PyObject *kwds)
{
	PyObject *seq;
	if (!PyArg_ParseTuple(args, "O:TrackLine", &seq)) {
		return -1;
	}
	PyObject *fast = PySequence_Fast(seq, "TrackLine(points): expected a sequence of 3D vectors");
	if (!fast) {
		return -1;
	}
	const Py_ssize_t n = PySequence_Fast_GET_SIZE(fast);
	if (n < 3) {
		Py_DECREF(fast);
		PyErr_SetString(PyExc_ValueError, "TrackLine(points): needs at least 3 points");
		return -1;
	}
	TrackLineData *d = new TrackLineData();
	d->points.resize(n);
	for (Py_ssize_t i = 0; i < n; i++) {
		if (!ReadVec3(PySequence_Fast_GET_ITEM(fast, i), d->points[i])) {
			Py_DECREF(fast);
			delete d;
			return -1;
		}
	}
	Py_DECREF(fast);

	auto dist = [](const Vec3d &a, const Vec3d &b) {
		return std::sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y) + (a.z - b.z) * (a.z - b.z));
	};
	d->cum.resize(n);
	d->cum[0] = 0.0;
	for (Py_ssize_t i = 1; i < n; i++) {
		d->cum[i] = d->cum[i - 1] + dist(d->points[i], d->points[i - 1]);
	}
	d->length = d->cum[n - 1] + dist(d->points[0], d->points[n - 1]);
	if (!(d->length > 0.0)) {
		delete d;
		PyErr_SetString(PyExc_ValueError, "TrackLine(points): zero length");
		return -1;
	}

	delete self->data;
	self->data = d;
	return 0;
}

bool CheckReady(KX_TrackLineObject *self)
{
	if (!self->data) {
		PyErr_SetString(PyExc_RuntimeError, "TrackLine not initialized");
		return false;
	}
	return true;
}

PyObject *TrackLine_point(KX_TrackLineObject *self, PyObject *arg)
{
	if (!CheckReady(self)) {
		return nullptr;
	}
	const double s = PyFloat_AsDouble(arg);
	if (s == -1.0 && PyErr_Occurred()) {
		return nullptr;
	}
	return MakeVector(PointAt(*self->data, s));
}

PyObject *TrackLine_side(KX_TrackLineObject *self, PyObject *arg)
{
	if (!CheckReady(self)) {
		return nullptr;
	}
	const double s = PyFloat_AsDouble(arg);
	if (s == -1.0 && PyErr_Occurred()) {
		return nullptr;
	}
	const Vec3d p = PointAt(*self->data, s);
	const Vec3d q = PointAt(*self->data, s + 2.0);
	/* (q - p) x (0, 0, 1) */
	const double sx = q.y - p.y, sy = -(q.x - p.x);
	const double l2 = sx * sx + sy * sy;
	if (l2 < 1e-6) {
		Py_RETURN_NONE;
	}
	const double l = std::sqrt(l2);
	return MakeVector({sx / l, sy / l, 0.0});
}

PyObject *TrackLine_locate(KX_TrackLineObject *self, PyObject *args)
{
	if (!CheckReady(self)) {
		return nullptr;
	}
	PyObject *pypos;
	int seg = -1, back = 0, ahead = 0;
	double lost = 0.0;
	if (!PyArg_ParseTuple(args, "O|iiid:locate", &pypos, &seg, &back, &ahead, &lost)) {
		return nullptr;
	}
	Vec3d pos;
	if (!ReadVec3(pypos, pos)) {
		return nullptr;
	}
	const TrackLineData &d = *self->data;
	const int n = (int)d.points.size();
	double bestD2 = 0.0, bestS = 0.0;
	int bestI = -1;
	if (seg >= 0) {
		for (int off = -back; off <= ahead; off++) {
			const int i = ((seg + off) % n + n) % n;
			double d2, s;
			Project(d, pos, i, d2, s);
			if (bestI < 0 || d2 < bestD2) {
				bestD2 = d2;
				bestS = s;
				bestI = i;
			}
		}
		if (bestI >= 0 && bestD2 < lost * lost) {
			return Py_BuildValue("ddi", bestD2, bestS, bestI);
		}
	}
	LocateGlobal(d, pos, bestD2, bestS, bestI);
	return Py_BuildValue("ddi", bestD2, bestS, bestI);
}

PyObject *TrackLine_setProfile(KX_TrackLineObject *self, PyObject *args)
{
	if (!CheckReady(self)) {
		return nullptr;
	}
	const char *name;
	PyObject *seq;
	if (!PyArg_ParseTuple(args, "sO:setProfile", &name, &seq)) {
		return nullptr;
	}
	PyObject *fast = PySequence_Fast(seq, "setProfile(name, values): expected a sequence of numbers");
	if (!fast) {
		return nullptr;
	}
	const Py_ssize_t n = PySequence_Fast_GET_SIZE(fast);
	if (n != (Py_ssize_t)self->data->points.size()) {
		Py_DECREF(fast);
		PyErr_SetString(PyExc_ValueError, "setProfile(name, values): one value per point is required");
		return nullptr;
	}
	std::vector<double> values(n);
	for (Py_ssize_t i = 0; i < n; i++) {
		values[i] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(fast, i));
		if (values[i] == -1.0 && PyErr_Occurred()) {
			Py_DECREF(fast);
			return nullptr;
		}
	}
	Py_DECREF(fast);
	self->data->profiles[name] = std::move(values);
	Py_RETURN_NONE;
}

PyObject *TrackLine_profile(KX_TrackLineObject *self, PyObject *args)
{
	if (!CheckReady(self)) {
		return nullptr;
	}
	const char *name;
	double s;
	if (!PyArg_ParseTuple(args, "sd:profile", &name, &s)) {
		return nullptr;
	}
	const TrackLineData &d = *self->data;
	const auto it = d.profiles.find(std::string_view(name));
	if (it == d.profiles.end()) {
		PyErr_Format(PyExc_KeyError, "TrackLine has no profile '%s'", name);
		return nullptr;
	}
	const std::vector<double> &arr = it->second;
	double t;
	const int i = SegmentAt(d, WrapS(s, d.length), t);
	const int j = (i + 1) % (int)arr.size();
	return PyFloat_FromDouble(arr[i] + (arr[j] - arr[i]) * t);
}

PyObject *TrackLine_get_length(KX_TrackLineObject *self, void *)
{
	if (!CheckReady(self)) {
		return nullptr;
	}
	return PyFloat_FromDouble(self->data->length);
}

Py_ssize_t TrackLine_len(KX_TrackLineObject *self)
{
	return self->data ? (Py_ssize_t)self->data->points.size() : 0;
}

PyMethodDef TrackLine_methods[] = {
	{"point", (PyCFunction)TrackLine_point, METH_O,
	 "point(s): point of the line s meters from the start (wraps around)."},
	{"side", (PyCFunction)TrackLine_side, METH_O,
	 "side(s): horizontal unit vector to the right of the line at s, or None."},
	{"locate", (PyCFunction)TrackLine_locate, METH_VARARGS,
	 "locate(pos, seg=-1, back=0, ahead=0, lost=0.0): (dist2, s, seg) of the closest segment. "
	 "With seg >= 0, searches seg-back..seg+ahead first and falls back to a global search "
	 "when the result is farther than lost."},
	{"setProfile", (PyCFunction)TrackLine_setProfile, METH_VARARGS,
	 "setProfile(name, values): one value per point, read back with profile()."},
	{"profile", (PyCFunction)TrackLine_profile, METH_VARARGS,
	 "profile(name, s): profile value interpolated at s meters."},
	{nullptr, nullptr, 0, nullptr}
};

PyGetSetDef TrackLine_getset[] = {
	{"length", (getter)TrackLine_get_length, nullptr, "Total length of the closed line (meters).", nullptr},
	{nullptr, nullptr, nullptr, nullptr, nullptr}
};

PySequenceMethods TrackLine_as_sequence = {
	(lenfunc)TrackLine_len,
};

PyTypeObject KX_TrackLine_Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"TrackLine",
	sizeof(KX_TrackLineObject),
};

} // namespace

void KX_TrackLine_Register(PyObject *dict)
{
	KX_TrackLine_Type.tp_dealloc = (destructor)TrackLine_dealloc;
	KX_TrackLine_Type.tp_flags = Py_TPFLAGS_DEFAULT;
	KX_TrackLine_Type.tp_doc = "TrackLine(points): closed polyline for racing AI.";
	KX_TrackLine_Type.tp_methods = TrackLine_methods;
	KX_TrackLine_Type.tp_getset = TrackLine_getset;
	KX_TrackLine_Type.tp_as_sequence = &TrackLine_as_sequence;
	KX_TrackLine_Type.tp_init = (initproc)TrackLine_init;
	KX_TrackLine_Type.tp_new = PyType_GenericNew;
	if (PyType_Ready(&KX_TrackLine_Type) < 0) {
		PyErr_Print();
		return;
	}
	PyDict_SetItemString(dict, "TrackLine", (PyObject *)&KX_TrackLine_Type);
}

#endif // WITH_PYTHON
