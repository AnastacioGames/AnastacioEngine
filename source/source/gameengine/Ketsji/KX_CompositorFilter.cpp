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

/** \file gameengine/Ketsji/KX_CompositorFilter.cpp
 *  \ingroup ketsji
 *
 * Phase 1 of Compositing in the game: the cheap compositor nodes become GLSL, following the
 * formulas of source/blender/compositor/operations. Values are read once at load, except the Value
 * and RGB nodes: they are uniforms named "comp_" + node name, set from Python with
 * scene.filterManager.compositor.setUniform(name, value).
 * Each node output is a function `vec4 cN_S(vec2 uv)`; floats travel in .x. Nodes that sample
 * their input at other places (Blur, Lens Distortion) call the upstream function there, so a
 * blurred mask costs its taps times the mask, which is cheap; a blur over a long chain is not.
 */

#include "KX_CompositorFilter.h"

#include <map>
#include <set>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <cctype>
#include <cstdlib>

#include "DNA_node_types.h"
#include "DNA_scene_types.h"
#include "DNA_color_types.h"
#include "DNA_texture_types.h"
#include "DNA_material_types.h"
#include "BKE_node.h"
#include "BLI_listbase.h"
#include "BLI_utildefines.h"

extern "C" {
#include "BKE_colortools.h"
#include "BKE_colorband.h"
}

namespace {

const int LUT_SIZE = 33;

std::string F(float v)
{
	if (!std::isfinite(v)) {
		v = 0.0f;
	}
	std::ostringstream s;
	s.precision(7);
	s << std::fixed << v;
	return s.str();
}

std::string V4(const float v[4])
{
	return "vec4(" + F(v[0]) + ", " + F(v[1]) + ", " + F(v[2]) + ", " + F(v[3]) + ")";
}

class Generator
{
public:
	/// Node outputs already drawn into a texture by an earlier stage: (node, output) -> cache index.
	typedef std::map<std::pair<bNode *, int>, int> CacheMap;

	Generator(bNodeTree *ntree, std::vector<std::string>& skipped, std::vector<KX_CompositorUniform>& uniforms,
	          const CacheMap *caches = nullptr)
		:m_tree(ntree), m_skipped(skipped), m_uniforms(uniforms), m_caches(caches)
	{
	}

	/// Node and output that feed \a sock, past reroutes and muted nodes; false when nothing does.
	bool Source(bNodeSocket *sock, bNode *& from, bNodeSocket *& fromsock)
	{
		bNodeLink *link = sock ? FindLink(sock) : nullptr;
		if (!link || !link->fromnode || !link->fromsock) {
			return false;
		}
		from = link->fromnode;
		fromsock = link->fromsock;
		for (int depth = 0; from && (from->type == NODE_REROUTE || (from->flag & NODE_MUTED)); ++depth) {
			bNodeSocket *in = (depth < 256) ? PassThrough(from, fromsock) : nullptr;
			bNodeLink *l = in ? FindLink(in) : nullptr;
			if (!l || !l->fromnode || !l->fromsock) {
				return false;
			}
			from = l->fromnode;
			fromsock = l->fromsock;
		}
		return from != nullptr;
	}

	/** Blur and Lens Distortion read their input at many places, and each read runs the whole chain
	 * before them again (a 7x7 blur after 8 color nodes cost 10 ms at 720p). An input that reads the
	 * render or another sampling node is drawn once into a texture by an earlier stage instead; a
	 * plain Render Layers input or a mask made only of math stays inline (cheaper than a pass). */
	void FindCaches(bNode *node, std::vector<std::pair<bNode *, int>>& order, std::set<bNode *>& seen)
	{
		if (!node || seen.count(node)) {
			return;
		}
		seen.insert(node);
		for (bNodeSocket *sock = (bNodeSocket *)node->inputs.first; sock; sock = sock->next) {
			bNode *from;
			bNodeSocket *fromsock;
			if (Source(sock, from, fromsock)) {
				FindCaches(from, order, seen);
			}
		}
		bNode *from;
		bNodeSocket *fromsock;
		if (node->type == CMP_NODE_GLARE) {
			// The bright part of a Glare is drawn into a mipmapped texture: Fog Glow sums its levels,
			// Streaks and Ghosts read it slightly blurred. Key: (glare node, -1).
			const std::pair<bNode *, int> key(node, -1);
			if (Source((bNodeSocket *)node->inputs.first, from, fromsock) &&
			    std::find(order.begin(), order.end(), key) == order.end()) {
				order.push_back(key);
			}
			return;
		}
		if (node->type != CMP_NODE_BLUR && node->type != CMP_NODE_LENSDIST) {
			return;
		}
		if (!Source((bNodeSocket *)node->inputs.first, from, fromsock) || from->type == CMP_NODE_R_LAYERS) {
			return;
		}
		std::set<bNode *> visited;
		if (!ReadsTextures(from, visited)) {
			return;
		}
		const std::pair<bNode *, int> key(from, BLI_findindex(&from->outputs, fromsock));
		if (std::find(order.begin(), order.end(), key) == order.end()) {
			order.push_back(key);  // post order: a cache comes after the caches it reads
		}
	}

	/// Expression (vec4) of the given input socket, at coordinate expression \a uv.
	std::string Input(bNode *node, int index, const std::string& uv)
	{
		bNodeSocket *sock = (bNodeSocket *)BLI_findlink(&node->inputs, index);
		if (!sock) {
			return "vec4(0.0)";
		}
		bNodeLink *link = FindLink(sock);
		if (!link || !link->fromnode || !link->fromsock) {
			return Default(sock);
		}
		bNode *from = link->fromnode;
		bNodeSocket *fromsock = link->fromsock;
		// Reroutes pass their input on, muted nodes the input of their internal link.
		for (int depth = 0; from && (from->type == NODE_REROUTE || (from->flag & NODE_MUTED)); ++depth) {
			bNodeSocket *in = (depth < 256) ? PassThrough(from, fromsock) : nullptr;
			if (!in && from->type != NODE_REROUTE) {
				return "vec4(0.0)";
			}
			bNodeLink *l = in ? FindLink(in) : nullptr;
			if (!l) {
				return in ? Convert(Default(in), in->type, sock->type) : Default(sock);
			}
			from = l->fromnode;
			fromsock = l->fromsock;
		}
		const int outIndex = BLI_findindex(&from->outputs, fromsock);
		if (m_caches) {
			auto it = m_caches->find(std::make_pair(from, outIndex));
			if (it != m_caches->end()) {
				m_usedCaches.insert(it->second);
				return Convert("texture(comp_cache" + std::to_string(it->second) + ", " + uv + ")",
				               fromsock->type, sock->type);
			}
		}
		const std::string name = Emit(from, outIndex);
		return Convert(name + "(" + uv + ")", fromsock->type, sock->type);
	}

	std::string Output(bNode *node, int index)
	{
		return (index == -1) ? EmitGlareBright(node) : Emit(node, index);
	}

	/// vec4 function of the bright part of a Glare input (GlareThresholdOperation).
	std::string EmitGlareBright(bNode *node)
	{
		const std::string name = "g" + std::to_string(Id(node)) + "_bright";
		if (m_done.count(name)) {
			return name;
		}
		m_done.insert(name);
		NodeGlare *g = (NodeGlare *)node->storage;
		const float threshold = g ? g->threshold : 1.0f;
		const std::string src = Input(node, 0, "uv");  // emits the upstream functions first
		m_code << "vec4 " << name << "(vec2 uv)\n{\n\tvec3 c = " << src << ".rgb;\n"
		       << "\tif (dot(c, vec3(0.2126, 0.7152, 0.0722)) < " << F(threshold) << ") return vec4(0.0, 0.0, 0.0, 1.0);\n"
		       << "\treturn vec4(max(c - " << F(threshold) << ", 0.0), 1.0);\n}\n\n";
		return name;
	}

	std::string Code() const
	{
		return m_code.str();
	}

	/// Declarations of the uniforms of the Value and RGB nodes and of the cache textures read.
	std::string UniformCode() const
	{
		std::string s;
		for (int k : m_usedCaches) {
			s += "uniform sampler2D comp_cache" + std::to_string(k) + ";\n";
		}
		for (const KX_CompositorUniform& u : m_uniforms) {
			s += (u.values.size() == 1 ? "uniform float " : "uniform vec4 ") + u.name + ";\n";
		}
		return s + "\n";
	}

	/// Input a reroute or a muted node hands to \a out (the node's internal link), null if none.
	static bNodeSocket *PassThrough(bNode *node, bNodeSocket *out)
	{
		if (node->type == NODE_REROUTE) {
			return (bNodeSocket *)node->inputs.first;
		}
		for (bNodeLink *link = (bNodeLink *)node->internal_links.first; link; link = link->next) {
			if (link->tosock == out) {
				return link->fromsock;
			}
		}
		return nullptr;
	}

	const std::set<int>& UsedCaches() const
	{
		return m_usedCaches;
	}

private:
	/// True when the node (or anything before it) reads the render or samples its input elsewhere.
	bool ReadsTextures(bNode *node, std::set<bNode *>& visited)
	{
		if (!node || visited.count(node)) {
			return false;
		}
		visited.insert(node);
		if (node->type == CMP_NODE_R_LAYERS || node->type == CMP_NODE_BLUR || node->type == CMP_NODE_LENSDIST ||
		    node->type == CMP_NODE_GLARE) {
			return true;
		}
		for (bNodeSocket *sock = (bNodeSocket *)node->inputs.first; sock; sock = sock->next) {
			bNode *from;
			bNodeSocket *fromsock;
			if (Source(sock, from, fromsock) && ReadsTextures(from, visited)) {
				return true;
			}
		}
		return false;
	}

	bNodeLink *FindLink(bNodeSocket *sock)
	{
		for (bNodeLink *link = (bNodeLink *)m_tree->links.first; link; link = link->next) {
			if (link->tosock == sock && (link->flag & NODE_LINK_VALID)) {
				return link;
			}
		}
		return nullptr;
	}

	static std::string Default(bNodeSocket *sock)
	{
		switch (sock->type) {
			case SOCK_FLOAT:
				return "vec4(" + F(((bNodeSocketValueFloat *)sock->default_value)->value) + ")";
			case SOCK_RGBA:
				return V4(((bNodeSocketValueRGBA *)sock->default_value)->value);
			case SOCK_VECTOR: {
				const float *v = ((bNodeSocketValueVector *)sock->default_value)->value;
				const float v4[4] = {v[0], v[1], v[2], 0.0f};
				return V4(v4);
			}
			default:
				return "vec4(0.0)";
		}
	}

	/// Color -> value is the RGB average, like the compositor; value -> color is gray, opaque.
	static std::string Convert(const std::string& expr, int from, int to)
	{
		if (from == SOCK_RGBA && to == SOCK_FLOAT) {
			return "vec4(comp_avg(" + expr + "))";
		}
		if (from == SOCK_FLOAT && to == SOCK_RGBA) {
			return "comp_gray(" + expr + ")";
		}
		return expr;
	}

	float SocketFloat(bNode *node, int index)
	{
		bNodeSocket *sock = (bNodeSocket *)BLI_findlink(&node->inputs, index);
		return (sock && sock->type == SOCK_FLOAT) ? ((bNodeSocketValueFloat *)sock->default_value)->value : 0.0f;
	}

	bool Linked(bNode *node, int index)
	{
		bNodeSocket *sock = (bNodeSocket *)BLI_findlink(&node->inputs, index);
		return sock && FindLink(sock);
	}

	std::string Emit(bNode *node, int out)
	{
		const std::string name = "c" + std::to_string(Id(node)) + "_" + std::to_string(out);
		if (m_done.count(name)) {
			return name;
		}
		m_done.insert(name);
		const std::string body = Body(node, out);
		m_code << "vec4 " << name << "(vec2 uv)\n{\n" << body << "}\n\n";
		return name;
	}

	int Id(bNode *node)
	{
		auto it = m_ids.find(node);
		if (it != m_ids.end()) {
			return it->second;
		}
		const int id = (int)m_ids.size();
		m_ids[node] = id;
		return id;
	}

	std::string Lut(const float *values)
	{
		std::string s = "float[" + std::to_string(LUT_SIZE) + "](";
		for (int i = 0; i < LUT_SIZE; ++i) {
			s += (i ? ", " : "") + F(values[i]);
		}
		return s + ")";
	}

	std::string Body(bNode *node, int out)
	{
		std::ostringstream b;
		// Inputs are evaluated first (each once), so the body below reads locals.
		auto in = [&](int i) { return Input(node, i, "uv"); };

		switch (node->type) {
			case CMP_NODE_R_LAYERS: {
				bNodeSocket *sock = (bNodeSocket *)BLI_findlink(&node->outputs, out);
				const std::string sname = sock ? sock->name : "";
				if (sname == "Image") {
					b << "\treturn comp_image(uv);\n";
				}
				else if (sname == "Alpha") {
					b << "\treturn vec4(comp_image(uv).a);\n";
				}
				else if (sname == "Depth") {
					b << "\treturn vec4(comp_depth(uv));\n";
				}
				else {
					Skip(std::string("Render Layers > ") + sname);
					b << "\treturn vec4(0.0);\n";
				}
				break;
			}
			case CMP_NODE_VALUE: {
				bNodeSocket *sock = (bNodeSocket *)node->outputs.first;
				const float v = ((bNodeSocketValueFloat *)sock->default_value)->value;
				b << "\treturn vec4(" << AddUniform(node, &v, 1) << ");\n";
				break;
			}
			case CMP_NODE_RGB: {
				bNodeSocket *sock = (bNodeSocket *)node->outputs.first;
				b << "\treturn " << AddUniform(node, ((bNodeSocketValueRGBA *)sock->default_value)->value, 4) << ";\n";
				break;
			}
			case CMP_NODE_MIX_RGB: {
				b << "\tfloat fac = " << in(0) << ".x;\n";
				b << "\tvec4 c1 = " << in(1) << ";\n\tvec4 c2 = " << in(2) << ";\n";
				if (node->custom2 & SHD_MIXRGB_USE_ALPHA) {
					b << "\tfac *= c2.a;\n";
				}
				b << "\tvec4 r = vec4(comp_mix(" << (int)node->custom1 << ", clamp(fac, 0.0, 1.0), c1.rgb, c2.rgb), c1.a);\n";
				if (node->custom2 & SHD_MIXRGB_CLAMP) {
					b << "\tr.rgb = clamp(r.rgb, 0.0, 1.0);\n";
				}
				b << "\treturn r;\n";
				break;
			}
			case CMP_NODE_ALPHAOVER: {
				b << "\tfloat fac = " << in(0) << ".x;\n";
				b << "\tvec4 c1 = " << in(1) << ";\n\tvec4 c2 = " << in(2) << ";\n";
				// AlphaOver{Premultiply,Key,Mixed}Operation: Key is Mixed with x = 1, Premultiply with x = 0.
				NodeTwoFloats *ntf = (NodeTwoFloats *)node->storage;
				const float x = (ntf && ntf->x != 0.0f) ? ntf->x : (node->custom1 ? 1.0f : 0.0f);
				b << "\tif (c2.a " << (x == 0.0f ? "<" : "<=") << " 0.0) return c1;\n";
				b << "\tif (fac == 1.0 && c2.a >= 1.0) return c2;\n";
				b << "\tfloat addfac = " << F(1.0f - x) << " + c2.a * " << F(x) << ";\n";
				b << "\tfloat mul = 1.0 - fac * c2.a;\n";
				b << "\treturn vec4(mul * c1.rgb + fac * addfac * c2.rgb, mul * c1.a + fac * c2.a);\n";
				break;
			}
			case CMP_NODE_BRIGHTCONTRAST: {
				b << "\tvec4 c = " << in(0) << ";\n";
				b << "\tfloat bright = " << in(1) << ".x / 100.0;\n";
				b << "\tfloat contrast = " << in(2) << ".x;\n";
				b << "\tfloat delta = contrast / 200.0;\n\tfloat a = 1.0 - delta * 2.0;\n\tfloat bb;\n";
				b << "\tif (contrast > 0.0) { a = 1.0 / a; bb = a * (bright - delta); }\n";
				b << "\telse { bb = a * (bright - delta); }\n";
				b << "\treturn vec4(a * c.rgb + bb, c.a);\n";
				break;
			}
			case CMP_NODE_GAMMA: {
				b << "\tvec4 c = " << in(0) << ";\n\tfloat g = " << in(1) << ".x;\n";
				b << "\treturn vec4(mix(c.rgb, pow(max(c.rgb, vec3(0.0)), vec3(g)), vec3(greaterThan(c.rgb, vec3(0.0)))), c.a);\n";
				break;
			}
			case CMP_NODE_INVERT: {
				b << "\tfloat fac = " << in(0) << ".x;\n\tvec4 c = " << in(1) << ";\n";
				if (node->custom1 & CMP_CHAN_RGB) {
					b << "\tc.rgb = mix(c.rgb, 1.0 - c.rgb, fac);\n";
				}
				if (node->custom1 & CMP_CHAN_A) {
					b << "\tc.a = mix(c.a, 1.0 - c.a, fac);\n";
				}
				b << "\treturn c;\n";
				break;
			}
			case CMP_NODE_HUE_SAT: {
				b << "\tvec4 c = " << in(0) << ";\n";
				b << "\tvec3 hsv = comp_rgb_to_hsv(c.rgb);\n";
				b << "\thsv.x = fract(hsv.x + " << in(1) << ".x + 0.5);\n";
				b << "\thsv.y = clamp(hsv.y * " << in(2) << ".x, 0.0, 1.0);\n";
				b << "\thsv.z *= " << in(3) << ".x;\n";
				b << "\treturn vec4(mix(c.rgb, comp_hsv_to_rgb(hsv), " << in(4) << ".x), c.a);\n";
				break;
			}
			case CMP_NODE_COLORBALANCE: {
				NodeColorBalance *n = (NodeColorBalance *)node->storage;
				b << "\tfloat fac = min(" << in(0) << ".x, 1.0);\n\tvec4 c = " << in(1) << ";\n";
				if (!n) {
					b << "\treturn c;\n";
					break;
				}
				if (node->custom1 == 0) {
					float lift[4], gammaInv[4], gain[4];
					for (int i = 0; i < 3; ++i) {
						lift[i] = 2.0f - n->lift[i];
						gammaInv[i] = (n->gamma[i] != 0.0f) ? 1.0f / n->gamma[i] : 1000000.0f;
						gain[i] = n->gain[i];
					}
					lift[3] = gammaInv[3] = gain[3] = 0.0f;
					b << "\tvec3 lift = " << V4(lift) << ".rgb;\n\tvec3 ginv = " << V4(gammaInv) << ".rgb;\n";
					b << "\tvec3 gain = " << V4(gain) << ".rgb;\n";
					b << "\tvec3 x = max(((comp_lin_to_srgb(c.rgb) - 1.0) * lift + 1.0) * gain, vec3(0.0));\n";
					b << "\tvec3 r = pow(comp_srgb_to_lin(x), ginv);\n";
				}
				else {
					float slope[4], offset[4], power[4];
					for (int i = 0; i < 3; ++i) {
						slope[i] = n->slope[i];
						offset[i] = n->offset[i] + n->offset_basis;
						power[i] = n->power[i];
					}
					slope[3] = offset[3] = power[3] = 0.0f;
					b << "\tvec3 r = pow(max(c.rgb * " << V4(slope) << ".rgb + " << V4(offset) << ".rgb, vec3(0.0)), "
					  << V4(power) << ".rgb);\n";
				}
				b << "\treturn vec4(mix(c.rgb, r, fac), c.a);\n";
				break;
			}
			case CMP_NODE_CURVE_RGB: {
				CurveMapping *cumap = (CurveMapping *)node->storage;
				b << "\tfloat fac = " << in(0) << ".x;\n\tvec4 c = " << in(1) << ";\n";
				if (!cumap) {
					b << "\treturn c;\n";
					break;
				}
				curvemapping_initialize(cumap);
				// ColorCurveOperation: channel curve, then the combined one (the premultiplied table).
				// When the editor left the tables premultiplied, the channel table already holds both.
				const bool premulled = (cumap->flag & CUMA_PREMULLED) != 0;
				auto curve = [&](int ch, float x) {
					const float v = curvemap_evaluateF(&cumap->cm[ch], x);
					return premulled ? v : curvemap_evaluateF(&cumap->cm[3], v);
				};
				float lut[3][LUT_SIZE];
				float ext[3][4];
				for (int ch = 0; ch < 3; ++ch) {
					// The LUT covers 0..1 or the wider range of the edited curve (Use Clipping off).
					const CurveMap *cm = &cumap->cm[ch];
					const float lo = std::min(0.0f, cm->mintable);
					const float hi = std::max(1.0f, cm->maxtable);
					for (int i = 0; i < LUT_SIZE; ++i) {
						lut[ch][i] = curve(ch, lo + (hi - lo) * (float)i / (LUT_SIZE - 1));
					}
					ext[ch][0] = lo;
					ext[ch][1] = hi;
					// Slopes past the range, so values outside keep following the extended curve.
					ext[ch][2] = lut[ch][0] - curve(ch, lo - 1.0f);
					ext[ch][3] = curve(ch, hi + 1.0f) - lut[ch][LUT_SIZE - 1];
				}
				b << "\tvec3 bl = " << in(2) << ".rgb;\n";
				b << "\tvec3 x = (c.rgb - bl) / max(" << in(3) << ".rgb - bl, vec3(1e-5));\n";
				b << "\tvec3 r;\n";
				const char *chan = "rgb";
				for (int ch = 0; ch < 3; ++ch) {
					b << "\tr." << chan[ch] << " = comp_curve(" << Lut(lut[ch]) << ", x." << chan[ch] << ", "
					  << F(ext[ch][0]) << ", " << F(ext[ch][1]) << ", " << F(ext[ch][2]) << ", " << F(ext[ch][3]) << ");\n";
				}
				b << "\tfac = clamp(fac, 0.0, 1.0);\n";
				b << "\treturn vec4(mix(c.rgb, r, fac), c.a);\n";
				break;
			}
			case CMP_NODE_VALTORGB: {
				ColorBand *coba = (ColorBand *)node->storage;
				b << "\tfloat fac = " << in(0) << ".x;\n";
				if (!coba) {
					b << "\treturn vec4(fac);\n";
					break;
				}
				float lut[4][LUT_SIZE];
				for (int i = 0; i < LUT_SIZE; ++i) {
					float col[4] = {0.0f, 0.0f, 0.0f, 0.0f};
					BKE_colorband_evaluate(coba, (float)i / (LUT_SIZE - 1), col);
					for (int ch = 0; ch < 4; ++ch) {
						lut[ch][i] = col[ch];
					}
				}
				b << "\tvec4 r = vec4(comp_lut(" << Lut(lut[0]) << ", fac), comp_lut(" << Lut(lut[1]) << ", fac), comp_lut("
				  << Lut(lut[2]) << ", fac), comp_lut(" << Lut(lut[3]) << ", fac));\n";
				b << (out == 1 ? "\treturn vec4(r.a);\n" : "\treturn r;\n");
				break;
			}
			case CMP_NODE_RGBTOBW:
				b << "\treturn vec4(comp_bw(" << in(0) << "));\n";
				break;
			case CMP_NODE_SEPRGBA:
				b << "\treturn vec4(" << in(0) << "[" << out << "]);\n";
				break;
			case CMP_NODE_COMBRGBA:
				b << "\treturn vec4(" << in(0) << ".x, " << in(1) << ".x, " << in(2) << ".x, " << in(3) << ".x);\n";
				break;
			case CMP_NODE_SETALPHA:
				b << "\treturn vec4(" << in(0) << ".rgb, " << in(1) << ".x);\n";
				break;
			case CMP_NODE_MATH: {
				b << "\tfloat a = " << in(0) << ".x;\n\tfloat b = " << in(1) << ".x;\n";
				b << "\tfloat r = comp_math(" << (int)node->custom1 << ", a, b);\n";
				if (node->custom2 & SHD_MATH_CLAMP) {
					b << "\tr = clamp(r, 0.0, 1.0);\n";
				}
				b << "\treturn vec4(r);\n";
				break;
			}
			case CMP_NODE_MASK_ELLIPSE:
			case CMP_NODE_MASK_BOX: {
				NodeEllipseMask *d = (NodeEllipseMask *)node->storage;  // same layout as NodeBoxMask
				b << "\tfloat mask = " << in(0) << ".x;\n\tfloat value = " << in(1) << ".x;\n";
				if (!d) {
					b << "\treturn vec4(mask);\n";
					break;
				}
				const float c = cosf(d->rotation), s = sinf(d->rotation);
				b << "\tfloat aspect = bgl_RenderedTextureWidth / bgl_RenderedTextureHeight;\n";
				b << "\tfloat dy = (uv.y - " << F(d->y) << ") / aspect;\n\tfloat dx = uv.x - " << F(d->x) << ";\n";
				b << "\tfloat rx = " << F(c) << " * dx + " << F(s) << " * dy;\n";
				b << "\tfloat ry = " << F(-s) << " * dx + " << F(c) << " * dy;\n";
				const float hw = d->width * 0.5f, hh = d->height * 0.5f;
				if (node->type == CMP_NODE_MASK_ELLIPSE) {
					b << "\tbool inside = (rx * rx) / " << F(hw * hw) << " + (ry * ry) / " << F(hh * hh) << " < 1.0;\n";
				}
				else {
					b << "\tbool inside = abs(rx) < " << F(hw) << " && abs(ry) < " << F(hh) << ";\n";
				}
				b << "\treturn vec4(comp_mask(" << (int)node->custom1 << ", inside, mask, value));\n";
				break;
			}
			case CMP_NODE_BLUR: {
				NodeBlurData *d = (NodeBlurData *)node->storage;
				if (!d) {
					b << "\treturn " << in(0) << ";\n";
					break;
				}
				// Size in pixels (or percent of the image), times the Size input; a 7x7 gaussian grid
				// spread over it: a light blur (smooth masks, glow), not the render's exact one.
				std::string rx, ry;
				if (d->relative) {
					rx = F(d->percentx * 0.01f) + " * 0.5";
					ry = F(d->percenty * 0.01f) + " * 0.5";
				}
				else {
					rx = F((float)d->sizex) + " / bgl_RenderedTextureWidth";
					ry = F((float)d->sizey) + " / bgl_RenderedTextureHeight";
				}
				b << "\tvec2 radius = vec2(" << rx << ", " << ry << ") * " << in(1) << ".x;\n";
				b << "\tvec4 sum = vec4(0.0);\n\tfloat wsum = 0.0;\n";
				b << "\tfor (int j = -3; j <= 3; ++j) {\n\t\tfor (int i = -3; i <= 3; ++i) {\n";
				b << "\t\t\tvec2 o = vec2(float(i), float(j)) / 3.0;\n";
				b << "\t\t\tfloat w = exp(-2.0 * dot(o, o));\n";
				b << "\t\t\tvec2 uv2 = uv + o * radius;\n";
				b << "\t\t\tsum += w * " << Input(node, 0, "uv2") << ";\n\t\t\twsum += w;\n";
				b << "\t\t}\n\t}\n\treturn sum / wsum;\n";
				break;
			}
			case CMP_NODE_LENSDIST: {
				// Screen lens distortion with dispersion (per channel radius), as in
				// ScreenLensDistortionOperation, without the jitter.
				NodeLensDist *d = (NodeLensDist *)node->storage;
				const bool fit = d && d->fit;
				b << "\tfloat dist = clamp(" << in(1) << ".x, -0.999, 1.0);\n";
				b << "\tfloat disp = 0.25 * clamp(" << in(2) << ".x, 0.0, 1.0);\n";
				b << "\tvec3 k = clamp(vec3(dist + disp, dist, dist - disp), -0.999, 1.0);\n";
				b << "\tfloat maxk = max(k.x, max(k.y, k.z));\n";
				b << "\tfloat sc = " << (fit ? "(maxk > 0.0) ? 1.0 / (1.0 + 2.0 * maxk) : " : "") << "1.0 / (1.0 + maxk);\n";
				b << "\tvec2 p = sc * (uv - 0.5) * 2.0;\n\tfloat r2 = dot(p, p);\n";
				b << "\tvec3 t = 1.0 - 4.0 * k * r2;\n";
				b << "\tif (t.x < 0.0 || t.y < 0.0 || t.z < 0.0) { return vec4(0.0); }\n";
				b << "\tvec3 dd = 1.0 / (1.0 + sqrt(t));\n";
				b << "\tvec2 uvr = p * dd.x + 0.5;\n\tvec2 uvg = p * dd.y + 0.5;\n\tvec2 uvb = p * dd.z + 0.5;\n";
				b << "\treturn vec4(" << Input(node, 0, "uvr") << ".r, " << Input(node, 0, "uvg") << ".g, "
				  << Input(node, 0, "uvb") << ".b, 1.0);\n";
				break;
			}
			case CMP_NODE_GLARE: {
				// Bright part (GlareThresholdOperation) spread by the glare type, then MixGlareOperation.
				// Fixed sample counts: Quality and Iterations of the render are not followed exactly.
				NodeGlare *g = (NodeGlare *)node->storage;
				if (!g) {
					b << "\treturn " << in(0) << ";\n";
					break;
				}
				// fn(p, lod): bright part at p, from the mipmapped texture when there is one.
				const std::string fn = "g" + std::to_string(Id(node)) + "_b";
				{
					std::string sample;
					if (m_caches) {
						auto it = m_caches->find(std::make_pair(node, -1));
						if (it != m_caches->end()) {
							m_usedCaches.insert(it->second);
							sample = "textureLod(comp_cache" + std::to_string(it->second) + ", p, lod).rgb";
						}
					}
					if (sample.empty()) {
						sample = EmitGlareBright(node) + "(p).rgb";  // no texture: no levels, lod unused
					}
					m_code << "vec3 " << fn << "(vec2 p, float lod)\n{\n\treturn " << sample << ";\n}\n\n";
				}
				b << "\tvec2 px = 1.0 / vec2(bgl_RenderedTextureWidth, bgl_RenderedTextureHeight);\n";
				b << "\tvec3 glare = vec3(0.0);\n";
				const float colmod = std::min(std::max(g->colmod, 0.0f), 1.0f);
				const float fade = std::min(std::max(g->fade, 0.75f), 1.0f);
				if (g->type == 1) {  // Fog Glow: wide soft glow, sum of the mip levels up to 2^size pixels
					const int maxLod = std::min(std::max((int)g->size, 6), 9) - 3;
					b << "\tfor (int l = 1; l <= " << maxLod << "; ++l) {\n"
					  << "\t\tvec2 o = px * exp2(float(l)) * 0.5;\n"
					  << "\t\tglare += 0.25 * (" << fn << "(uv + o, float(l)) + " << fn << "(uv - o, float(l)) + "
					  << fn << "(uv + vec2(o.x, -o.y), float(l)) + " << fn << "(uv - vec2(o.x, -o.y), float(l)));\n"
					  << "\t}\n\tglare *= " << F(2.0f / (float)maxLod) << ";\n";
				}
				else if (g->type == 3) {  // Ghosts: blurred copies mirrored through the center, tinted
					b << "\tconst float sc[6] = float[6](-1.0, -0.62, -0.35, 0.28, 0.55, 0.85);\n";
					b << "\tconst vec3 tint[3] = vec3[3](vec3(1.0, 0.6, 0.4), vec3(0.6, 1.0, 0.5), vec3(0.5, 0.6, 1.0));\n";
					b << "\tfor (int i = 0; i < 6; ++i) {\n"
					  << "\t\tvec2 p = 0.5 + (uv - 0.5) * sc[i];\n"
					  << "\t\tvec3 s = " << fn << "(p, 3.0);\n"
					  << "\t\tglare += s * mix(vec3(1.0), tint[i - 3 * (i / 3)], " << F(colmod) << ") * pow(" << F(fade) << ", float(i) * 4.0);\n"
					  << "\t}\n\tglare *= 0.3;\n";
				}
				else {  // Streaks / Simple Star: lines of light fading away from each bright pixel
					const bool star = (g->type == 0);
					const int count = star ? 4 : std::min(std::max((int)g->streaks, 1), 16);
					const float offset = star ? (g->star_45 ? 0.7853982f : 0.0f) : g->angle_ofs;
					const float length = std::min(std::pow(4.0f, (float)std::min(std::max((int)g->iter, 2), 5)), 512.0f);
					b << "\tfor (int s = 0; s < " << count << "; ++s) {\n"
					  << "\t\tfloat a = " << F(offset) << " + float(s) * " << F(6.2831853f / (float)count) << ";\n"
					  << "\t\tvec2 dir = vec2(cos(a), sin(a)) * px;\n"
					  << "\t\tfor (int i = 1; i <= 16; ++i) {\n"
					  << "\t\t\tfloat t = float(i) / 16.0;\n"
					  << "\t\t\tfloat w = pow(" << F(fade) << ", t * 64.0);\n"
					  << "\t\t\tvec3 tint = mix(vec3(1.0), vec3(1.0, 0.5 + 0.5 * (1.0 - t), 0.25 + 0.75 * (1.0 - t)), " << F(colmod) << ");\n"
					  << "\t\t\tglare += w * tint * " << fn << "(uv + dir * t * " << F(length) << ", 1.0);\n"
					  << "\t\t}\n\t}\n\tglare *= " << F(2.0f / (float)count) << ";\n";
				}
				b << "\tvec4 c1 = " << in(0) << ";\n";
				b << "\tfloat v = " << F(0.5f + g->mix * 0.5f) << ";\n";
				b << "\tfloat mf = 2.0 - 2.0 * abs(v - 0.5);\n";
				b << "\tvec3 base = max(c1.rgb, 0.0);\n";
				b << "\treturn vec4(mf * max(base + v * (glare - base), 0.0), c1.a);\n";
				break;
			}
			case CMP_NODE_COMPOSITE:
			case CMP_NODE_VIEWER:
				b << "\treturn " << in(0) << ";\n";
				break;
			default: {
				Skip(node->name);
				bNodeSocket *first = (bNodeSocket *)node->inputs.first;
				b << "\treturn " << (first ? in(0) : std::string("vec4(0.0)")) << ";\n";
				break;
			}
		}
		return b.str();
	}

	/// Uniform "comp_" + node name (other characters become '_'); a clash gets the node id.
	std::string AddUniform(bNode *node, const float *values, int count)
	{
		std::string name = "comp_";
		for (const char *c = node->name; *c; ++c) {
			const unsigned char ch = (unsigned char)*c;
			name += (ch < 128 && isalnum(ch)) ? *c : '_';
		}
		// A clash gets the node id, then a counter, until no other uniform has the name.
		auto taken = [&](const std::string& n) {
			for (const KX_CompositorUniform& u : m_uniforms) {
				if (u.name == n) {
					return true;
				}
			}
			return false;
		};
		if (taken(name)) {
			const std::string base = name + "_" + std::to_string(Id(node));
			name = base;
			for (int i = 2; taken(name); ++i) {
				name = base + "_" + std::to_string(i);
			}
		}
		KX_CompositorUniform u;
		u.name = name;
		for (int i = 0; i < count; ++i) {
			u.values.push_back(std::isfinite(values[i]) ? values[i] : 0.0f);
		}
		m_uniforms.push_back(u);
		return name;
	}

	void Skip(const std::string& name)
	{
		m_skipped.push_back(name);
	}

	bNodeTree *m_tree;
	std::vector<std::string>& m_skipped;
	std::vector<KX_CompositorUniform>& m_uniforms;
	const CacheMap *m_caches;
	std::set<int> m_usedCaches;
	std::map<bNode *, int> m_ids;
	std::set<std::string> m_done;
	std::ostringstream m_code;
};

const char *compositorHeader = R"GLSL(
#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;
out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform float bgl_RenderedTextureWidth;
uniform float bgl_RenderedTextureHeight;
uniform mat4 bgl_ProjectionMatrix;

vec4 comp_image(vec2 uv)
{
	return texture(bgl_RenderedTexture, uv);
}

/* Distance from the camera plane, like the Depth output of the render (perspective). */
float comp_depth(vec2 uv)
{
	float ndc = texture(bgl_DepthTexture, uv).r * 2.0 - 1.0;
	if (bgl_ProjectionMatrix[3][3] == 1.0) {
		/* Orthographic: ndc = P22 * z + P32. */
		return (bgl_ProjectionMatrix[3][2] - ndc) / bgl_ProjectionMatrix[2][2];
	}
	return bgl_ProjectionMatrix[3][2] / (ndc + bgl_ProjectionMatrix[2][2]);
}

float comp_bw(vec4 c)
{
	return dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
}

float comp_avg(vec4 c)
{
	return (c.r + c.g + c.b) / 3.0;
}

vec4 comp_gray(vec4 v)
{
	return vec4(v.xxx, 1.0);
}

vec3 comp_lin_to_srgb(vec3 c)
{
	return mix(c * 12.92, 1.055 * pow(max(c, vec3(0.0)), vec3(1.0 / 2.4)) - 0.055, vec3(greaterThan(c, vec3(0.0031308))));
}

vec3 comp_srgb_to_lin(vec3 c)
{
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), vec3(greaterThan(c, vec3(0.04045))));
}

vec3 comp_rgb_to_hsv(vec3 c)
{
	vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
	vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
	vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
	float d = q.x - min(q.w, q.y);
	float e = 1.0e-10;
	return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 comp_hsv_to_rgb(vec3 c)
{
	vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
	return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}

float comp_lut(float lut[33], float x)
{
	float f = clamp(x, 0.0, 1.0) * 32.0;
	int i = int(min(floor(f), 31.0));
	return mix(lut[i], lut[i + 1], f - float(i));
}

/* LUT over lo..hi with straight lines outside (slopes per unit below lo and above hi). */
float comp_curve(float lut[33], float x, float lo, float hi, float slopeLow, float slopeHigh)
{
	if (x < lo) return lut[0] + slopeLow * (x - lo);
	if (x > hi) return lut[32] + slopeHigh * (x - hi);
	return comp_lut(lut, (x - lo) / (hi - lo));
}

/* Blend modes of the Mix node (MA_RAMP_*), the same formulas as the shader nodes. */
vec3 comp_mix(int type, float fac, vec3 c1, vec3 c2)
{
	float facm = 1.0 - fac;
	if (type == 1) return c1 + fac * c2;                                    /* Add */
	if (type == 2) return c1 * (facm + fac * c2);                           /* Multiply */
	if (type == 3) return c1 - fac * c2;                                    /* Subtract */
	if (type == 4) return 1.0 - (facm + fac * (1.0 - c2)) * (1.0 - c1);    /* Screen */
	if (type == 5) {                                                        /* Divide */
		vec3 d = facm * c1 + fac * c1 / mix(c2, vec3(1.0), vec3(equal(c2, vec3(0.0))));
		return mix(d, vec3(0.0), vec3(equal(c2, vec3(0.0))));
	}
	if (type == 6) return mix(c1, abs(c1 - c2), fac);                       /* Difference */
	if (type == 7) return min(c1, c2 * fac + c1 * facm);                    /* Darken */
	if (type == 8) return max(c1, c2 * fac);                                /* Lighten */
	if (type == 9) {                                                        /* Overlay */
		vec3 lo = c1 * (facm + 2.0 * fac * c2);
		vec3 hi = 1.0 - (facm + 2.0 * fac * (1.0 - c2)) * (1.0 - c1);
		return mix(lo, hi, vec3(greaterThanEqual(c1, vec3(0.5))));
	}
	if (type == 10) {                                                       /* Dodge */
		vec3 t = 1.0 - fac * c2;
		vec3 r = mix(vec3(1.0), min(c1 / max(t, vec3(1e-20)), vec3(1.0)), vec3(greaterThan(t, vec3(0.0))));
		return mix(r, vec3(0.0), vec3(equal(c1, vec3(0.0))));
	}
	if (type == 11) {                                                       /* Burn */
		vec3 t = facm + fac * c2;
		vec3 r = clamp(1.0 - (1.0 - c1) / max(t, vec3(1e-20)), 0.0, 1.0);
		return mix(vec3(0.0), r, vec3(greaterThan(t, vec3(0.0))));
	}
	if (type == 12 || type == 13 || type == 14 || type == 15) {             /* Hue, Saturation, Value, Color */
		vec3 h1 = comp_rgb_to_hsv(c1);
		vec3 h2 = comp_rgb_to_hsv(c2);
		vec3 h = h1;
		if (type == 12) h.x = h2.x;
		if (type == 13) h.y = h2.y;
		if (type == 14) h.z = h2.z;
		if (type == 15) h.xy = h2.xy;
		return mix(c1, comp_hsv_to_rgb(h), fac);
	}
	if (type == 16) {                                                       /* Soft Light */
		vec3 scr = 1.0 - (1.0 - c2) * (1.0 - c1);
		return facm * c1 + fac * ((1.0 - c1) * c2 * c1 + c1 * scr);
	}
	if (type == 17) return c1 + fac * (2.0 * c2 - 1.0);                     /* Linear Light */
	return mix(c1, c2, fac);                                                /* Mix */
}

float comp_math(int op, float a, float b)
{
	if (op == 0) return a + b;
	if (op == 1) return a - b;
	if (op == 2) return a * b;
	if (op == 3) return (b != 0.0) ? a / b : 0.0;
	if (op == 4) return sin(a);
	if (op == 5) return cos(a);
	if (op == 6) return tan(a);
	if (op == 7) return (a >= -1.0 && a <= 1.0) ? asin(a) : 0.0;
	if (op == 8) return (a >= -1.0 && a <= 1.0) ? acos(a) : 0.0;
	if (op == 9) return atan(a);
	if (op == 10) return (a >= 0.0 || b == floor(b)) ? pow(abs(a), b) * ((a < 0.0 && mod(b, 2.0) != 0.0) ? -1.0 : 1.0) : 0.0;
	if (op == 11) return (a > 0.0 && b > 0.0) ? log(a) / log(b) : 0.0;
	if (op == 12) return min(a, b);
	if (op == 13) return max(a, b);
	if (op == 14) return floor(a + 0.5);
	if (op == 15) return (a < b) ? 1.0 : 0.0;
	if (op == 16) return (a > b) ? 1.0 : 0.0;
	if (op == 17) return (b != 0.0) ? a - b * trunc(a / b) : 0.0;  /* fmod */
	if (op == 18) return abs(a);
	if (op == 19) return atan(a, b);
	if (op == 20) return floor(a);
	if (op == 21) return ceil(a);
	if (op == 22) return fract(a);
	if (op == 23) return (a > 0.0) ? sqrt(a) : 0.0;
	return a;
}

/* Box and Ellipse Mask: Add, Subtract, Multiply, Not. */
float comp_mask(int type, bool inside, float mask, float value)
{
	if (type == 0) return inside ? max(mask, value) : mask;
	if (type == 1) return inside ? clamp(mask - value, 0.0, 1.0) : mask;
	if (type == 2) return inside ? mask * value : 0.0;
	return inside ? ((mask > 0.0) ? 0.0 : value) : mask;
}

)GLSL";

bNode *FindOutput(bNodeTree *ntree)
{
	bNode *viewer = nullptr;
	for (bNode *node = (bNode *)ntree->nodes.first; node; node = node->next) {
		if (node->flag & NODE_MUTED) {
			continue;
		}
		if (node->type == CMP_NODE_COMPOSITE && (node->flag & NODE_DO_OUTPUT)) {
			return node;
		}
		if (node->type == CMP_NODE_COMPOSITE && !viewer) {
			viewer = node;
		}
	}
	if (viewer) {
		return viewer;
	}
	for (bNode *node = (bNode *)ntree->nodes.first; node; node = node->next) {
		if (node->type == CMP_NODE_VIEWER && !(node->flag & NODE_MUTED) && (node->flag & NODE_DO_OUTPUT)) {
			return node;
		}
	}
	return nullptr;
}

} // namespace

std::vector<KX_CompositorStage> KX_BuildCompositorShaders(Scene *scene, std::vector<std::string>& skipped)
{
	if (!scene || !scene->use_nodes || !scene->nodetree) {
		return {};
	}
	bNode *output = FindOutput(scene->nodetree);
	if (!output) {
		return {};
	}
	bNodeSocket *image = (bNodeSocket *)output->inputs.first;
	// Nothing linked, or the default tree (Render Layers > Image straight into the output, maybe
	// through reroutes): no pass, the frame stays as it is.
	bNodeSocket *sock = image;
	for (int depth = 0; sock && depth < 64; ++depth) {
		bNodeLink *found = nullptr;
		for (bNodeLink *link = (bNodeLink *)scene->nodetree->links.first; link; link = link->next) {
			if (link->tosock == sock && (link->flag & NODE_LINK_VALID)) {
				found = link;
				break;
			}
		}
		if (!found || !found->fromnode || !found->fromsock) {
			return {};
		}
		bNode *from = found->fromnode;
		if (from->type == NODE_REROUTE || (from->flag & NODE_MUTED)) {
			sock = Generator::PassThrough(from, found->fromsock);
			if (!sock) {
				break;
			}
			continue;
		}
		if (from->type == CMP_NODE_R_LAYERS && STREQ(found->fromsock->name, "Image")) {
			return {};
		}
		break;
	}

	const char *mainStart =
	    "void main()\n{\n#ifdef USE_CORE_PROFILE\n\tvec2 uv = texCoordVarying;\n#else\n\tvec2 uv = gl_TexCoord[0].st;\n#endif\n";

	// Caches first (deeper ones before the ones that read them), then the tree itself.
	std::vector<std::pair<bNode *, int>> order;
	{
		std::vector<KX_CompositorUniform> unusedUniforms;
		std::vector<std::string> unusedSkipped;
		Generator scan(scene->nodetree, unusedSkipped, unusedUniforms);
		std::set<bNode *> seen;
		scan.FindCaches(output, order, seen);
	}
	// Debug: RANGE_COMPOSITOR_NO_CACHE=1 keeps every chain inline (to compare images and timings).
	if (const char *off = getenv("RANGE_COMPOSITOR_NO_CACHE")) {
		if (off[0] && off[0] != '0') {
			order.clear();
		}
	}
	if (order.size() > (size_t)KX_COMPOSITOR_MAX_CACHES) {
		order.resize(KX_COMPOSITOR_MAX_CACHES);  // past that the rest stays inline (slower, same image)
	}

	std::vector<KX_CompositorStage> stages;
	Generator::CacheMap caches;
	std::set<std::string> skippedSet;
	for (size_t i = 0; i <= order.size(); ++i) {
		const bool last = (i == order.size());
		KX_CompositorStage stage;
		std::vector<std::string> stageSkipped;
		Generator gen(scene->nodetree, stageSkipped, stage.uniforms, &caches);
		const std::string out = last ? gen.Output(output, 0) : gen.Output(order[i].first, order[i].second);
		stage.shader = compositorHeader;
		stage.shader += gen.UniformCode();
		stage.shader += gen.Code();
		stage.shader += mainStart;
		stage.shader += "\tvec4 c = " + out + "(uv);\n";
		// The compositor's alpha does not belong on the screen: keep the frame opaque like the render.
		stage.shader += last ? "\tgl_FragColor = vec4(c.rgb, 1.0);\n}\n" : "\tgl_FragColor = c;\n}\n";
		stage.caches.assign(gen.UsedCaches().begin(), gen.UsedCaches().end());
		stage.mipmap = !last && order[i].second == -1;
		for (const std::string& name : stageSkipped) {
			if (skippedSet.insert(name).second) {
				skipped.push_back(name);
			}
		}
		stages.push_back(stage);
		if (!last) {
			caches[order[i]] = (int)i;
		}
	}
	return stages;
}
