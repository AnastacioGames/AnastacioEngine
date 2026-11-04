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

/** \file gameengine/Ketsji/KX_PyTrack.cpp
 *  \ingroup ketsji
 *
 * Range.track: dado de pista do Track Tool (docs/plano-track-tool.md, "Contrato entre módulos").
 *
 * A ferramenta do editor cozinha uma tabela por amostra no Text "TRACK_<nome>.json" (formato v1).
 * Aqui esse Text é lido do Main do jogo (e dos arquivos do LibLoad) no primeiro get(), guardado por
 * nome e consultado em C++. A semântica é a de range_track/runtime.py (referência em Python puro);
 * os dois precisam dar o mesmo resultado (tolerância 1 mm), conferido por
 * tools/debug/track_tool/ (vetores de referência).
 *
 * project() segue os passos 1-5 descritos em runtime.py: amostra mais próxima (com peso na altura)
 * por uma grade XY em anéis, depois os 4 segmentos em volta, cada um resolvido por uma equação de
 * 2º grau (ponto cuja lateral interpolada passa pela posição).
 */

#include "KX_PyTrack.h"

#ifdef WITH_PYTHON

#include "EXP_ListValue.h"
#include "EXP_StringValue.h"
#include "BL_Converter.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "KX_PyMath.h"

#include "CM_Message.h"

#include "cJSON.h"

extern "C" {
#include "BKE_global.h"
#include "BKE_main.h"
#include "BKE_text.h"
#include "DNA_text_types.h"
#include "MEM_guardedalloc.h"
}

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <map>
#include <memory>
#include <string>
#include <vector>

namespace {

const char *const kTextPrefix = "TRACK_";
const char *const kTextSuffix = ".json";
/// isOnRoad(): altura plausível em relação à superfície inclinada (m), como runtime.py.
const double kHeightTol = 3.0;

struct TrackData {
	std::string name;
	double length = 0.0;
	bool cyclic = false;
	double step = 1.0;
	int count = 0;

	/// Arrays por amostra (formato v1). Todos com `count` itens.
	std::vector<double> s, px, py, pz, tx, ty, tz, lx, ly, bank, wl, wr, el, er, race;
	std::vector<int> surface;
	std::vector<std::string> surfaces;

	/// Grade XY das amostras: células de `cell` metros a partir de (gx0, gy0), itens em CSR.
	double gx0 = 0.0, gy0 = 0.0, cell = 1.0;
	int nx = 0, ny = 0;
	std::vector<int> cellStart;
	std::vector<int> cellItems;
};

/* -------------------------------------------------------------------- */
/* Interpolação por s */

struct SamplePos {
	int i, j;
	double t;
};

/// Módulo do Python (não negativo para divisor positivo).
double WrapS(double s, double length)
{
	double r = std::fmod(s, length);
	if (r < 0.0) {
		r += length;
	}
	return r;
}

/// Ponto final (em s) do segmento que começa na amostra i.
double SegmentEndS(const TrackData &d, int i)
{
	return (i + 1 < d.count) ? d.s[i + 1] : d.length;
}

int SegmentEndIndex(const TrackData &d, int i)
{
	return (i + 1 < d.count) ? i + 1 : 0;
}

SamplePos Locate(const TrackData &d, double s)
{
	if (d.cyclic && d.length > 0.0) {
		s = WrapS(s, d.length);
	}
	else {
		s = std::max(d.s.front(), std::min(d.s.back(), s));
	}
	int i = int(std::upper_bound(d.s.begin(), d.s.end(), s) - d.s.begin()) - 1;
	i = std::max(0, std::min(d.count - 1, i));
	if (i == d.count - 1 && !d.cyclic) {
		return {i, i, 0.0};
	}
	const int j = SegmentEndIndex(d, i);
	const double s0 = d.s[i], s1 = SegmentEndS(d, i);
	const double t = (s1 > s0) ? (s - s0) / (s1 - s0) : 0.0;
	return {i, j, std::max(0.0, std::min(1.0, t))};
}

inline double Lerp(const std::vector<double> &a, const SamplePos &p)
{
	return a[p.i] + (a[p.j] - a[p.i]) * p.t;
}

void PointAt(const TrackData &d, const SamplePos &p, double out[3])
{
	out[0] = Lerp(d.px, p);
	out[1] = Lerp(d.py, p);
	out[2] = Lerp(d.pz, p);
}

void TangentAt(const TrackData &d, const SamplePos &p, double out[3])
{
	out[0] = Lerp(d.tx, p);
	out[1] = Lerp(d.ty, p);
	out[2] = Lerp(d.tz, p);
	const double l = std::sqrt(out[0] * out[0] + out[1] * out[1] + out[2] * out[2]);
	if (l > 1e-12) {
		out[0] /= l;
		out[1] /= l;
		out[2] /= l;
	}
}

/// Lateral horizontal (esquerda) interpolada e normalizada.
void LateralAt(const TrackData &d, const SamplePos &p, double out[2])
{
	out[0] = Lerp(d.lx, p);
	out[1] = Lerp(d.ly, p);
	const double l = std::sqrt(out[0] * out[0] + out[1] * out[1]);
	if (l > 1e-12) {
		out[0] /= l;
		out[1] /= l;
	}
}

/* -------------------------------------------------------------------- */
/* Projeção: passos 1-5 da semântica de runtime.py */

/// Resultado de project() com os intermediários que isOnRoad() usa.
struct Projection {
	double s;   ///< metros percorridos no ponto projetado
	double u;   ///< deslocamento lateral (+ = esquerda)
	double e2;  ///< resto² fora da lateral (XY): > 0 além do começo/fim da pista aberta
	double dz;  ///< altura em relação à superfície inclinada (0 sem z)
};

/// Grade XY das amostras (só acelera a busca da amostra mais próxima; resultado exato).
void BuildGrid(TrackData &d)
{
	double minx = std::numeric_limits<double>::max(), miny = minx;
	double maxx = -minx, maxy = -minx;
	for (int k = 0; k < d.count; ++k) {
		minx = std::min(minx, d.px[k]);
		maxx = std::max(maxx, d.px[k]);
		miny = std::min(miny, d.py[k]);
		maxy = std::max(maxy, d.py[k]);
	}
	/* 12 m como a referência; numa pista enorme a célula cresce para limitar a memória. */
	double cell = 12.0;
	const double maxCells = double(1 << 20);
	if (((maxx - minx) / cell + 1.0) * ((maxy - miny) / cell + 1.0) > maxCells) {
		cell = std::sqrt((maxx - minx) * (maxy - miny) / maxCells) * 1.05;
	}
	d.cell = cell;
	d.gx0 = minx;
	d.gy0 = miny;
	d.nx = int((maxx - minx) / cell) + 1;
	d.ny = int((maxy - miny) / cell) + 1;

	const int ncell = d.nx * d.ny;
	std::vector<int> cellOf(d.count);
	d.cellStart.assign(ncell + 1, 0);
	for (int k = 0; k < d.count; ++k) {
		const int cx = std::min(d.nx - 1, int((d.px[k] - d.gx0) / cell));
		const int cy = std::min(d.ny - 1, int((d.py[k] - d.gy0) / cell));
		cellOf[k] = cy * d.nx + cx;
		++d.cellStart[cellOf[k] + 1];
	}
	for (int c = 0; c < ncell; ++c) {
		d.cellStart[c + 1] += d.cellStart[c];
	}
	d.cellItems.resize(d.count);
	std::vector<int> fill(d.cellStart.begin(), d.cellStart.end() - 1);
	for (int k = 0; k < d.count; ++k) {
		d.cellItems[fill[cellOf[k]]++] = k;
	}
}

/// Passo 1: amostra de menor m = dx² + dy² + (2·dz)² (sem z: só XY); empate fica com o menor k.
int NearestSample(const TrackData &d, double x, double y, double z, bool hasZ)
{
	double best = std::numeric_limits<double>::infinity();
	int bk = -1;
	auto visit = [&](int gx, int gy) {
		if (gx < 0 || gy < 0 || gx >= d.nx || gy >= d.ny) {
			return;
		}
		const int c = gy * d.nx + gx;
		for (int it = d.cellStart[c]; it < d.cellStart[c + 1]; ++it) {
			const int k = d.cellItems[it];
			const double dx = d.px[k] - x;
			const double dy = d.py[k] - y;
			double m = dx * dx + dy * dy;
			if (hasZ) {
				const double dz = d.pz[k] - z;
				m = dx * dx + dy * dy + 4.0 * dz * dz;
			}
			if (m <= best && (m < best || k < bk)) {
				best = m;
				bk = k;
			}
		}
	};
	/* Posição muito longe: limita o índice para não estourar int (o limite de distância só
	 * fica mais conservador). */
	const double lim = 1e8;
	const int cx = int(std::max(-lim, std::min(lim, std::floor((x - d.gx0) / d.cell))));
	const int cy = int(std::max(-lim, std::min(lim, std::floor((y - d.gy0) / d.cell))));
	for (int r = std::max({0, -cx, cx - (d.nx - 1), -cy, cy - (d.ny - 1)});; ++r) {
		if (r == 0) {
			visit(cx, cy);
		}
		else {
			const int xlo = std::max(cx - r, 0), xhi = std::min(cx + r, d.nx - 1);
			const int ylo = std::max(cy - r + 1, 0), yhi = std::min(cy + r - 1, d.ny - 1);
			for (int xx = xlo; xx <= xhi; ++xx) {
				visit(xx, cy - r);
				visit(xx, cy + r);
			}
			for (int yy = ylo; yy <= yhi; ++yy) {
				visit(cx - r, yy);
				visit(cx + r, yy);
			}
		}
		const double bound = r * d.cell;
		if (bk >= 0 && best <= bound * bound) {
			break;
		}
		if (cx - r <= 0 && cx + r >= d.nx - 1 && cy - r <= 0 && cy + r >= d.ny - 1) {
			break;
		}
	}
	return bk;
}

struct SegmentFit {
	/// Nota comparada em ordem: rank 0 = posição dentro da seção do segmento (valor u² + (2·dz)²),
	/// rank 1 = fora dela (valor e²).
	int rank;
	double note, t, u, e2, dz;

	bool BetterThan(const SegmentFit &o) const
	{
		return rank < o.rank || (rank == o.rank && note < o.note);
	}
};

/// Passos 3 e 4 no segmento i: t onde p - P(t) é paralelo à lateral interpolada L(t).
SegmentFit SolveSegment(const TrackData &d, int i, double x, double y, double z, bool hasZ)
{
	const int j = SegmentEndIndex(d, i);
	const double x0 = d.px[i], y0 = d.py[i];
	const double Dx = d.px[j] - x0, Dy = d.py[j] - y0;
	const double L0x = d.lx[i], L0y = d.ly[i];
	const double dLx = d.lx[j] - L0x, dLy = d.ly[j] - L0y;
	const double qx = x - x0, qy = y - y0;
	const double dd = Dx * Dx + Dy * Dy;
	const double t_o = (dd >= 1e-12) ? (qx * Dx + qy * Dy) / dd : 0.0;
	const double A = -(Dx * dLy - Dy * dLx);
	const double B = (qx * dLy - qy * dLx) - (Dx * L0y - Dy * L0x);
	const double C = qx * L0y - qy * L0x;
	const double lo = -1e-6, hi = 1.0 + 1e-6;
	bool found = false;
	double t = 0.0;
	if (std::fabs(A) < 1e-12) {
		if (std::fabs(B) >= 1e-12) {
			const double r1 = -C / B;
			if (lo <= r1 && r1 <= hi) {
				t = r1;
				found = true;
			}
		}
	}
	else {
		const double disc = B * B - 4.0 * A * C;
		if (disc >= 0.0) {
			const double Q = -0.5 * (B + ((B >= 0.0) ? std::sqrt(disc) : -std::sqrt(disc)));
			const double r1 = Q / A;
			if (lo <= r1 && r1 <= hi) {
				t = r1;
				found = true;
			}
			if (Q != 0.0) {
				const double r2 = C / Q;
				if (lo <= r2 && r2 <= hi && (!found || std::fabs(r2 - t_o) < std::fabs(t - t_o))) {
					t = r2;
					found = true;
				}
			}
		}
	}
	if (!found) {
		t = t_o;
	}
	t = std::max(0.0, std::min(1.0, t));

	const double cx = x0 + Dx * t, cy = y0 + Dy * t;
	double Lx = L0x + dLx * t, Ly = L0y + dLy * t;
	const double ll = std::sqrt(Lx * Lx + Ly * Ly);
	if (ll > 1e-12) {
		Lx /= ll;
		Ly /= ll;
	}
	const double ox = x - cx, oy = y - cy;
	const double u = ox * Lx + oy * Ly;
	const double ex = ox - u * Lx, ey = oy - u * Ly;
	const double e2 = ex * ex + ey * ey;
	double dz = 0.0;
	if (hasZ) {
		const double cz = d.pz[i] + (d.pz[j] - d.pz[i]) * t;
		const double zs = cz - u * std::tan(d.bank[i] + (d.bank[j] - d.bank[i]) * t);
		dz = z - zs;
	}
	if (e2 < 1e-8) {
		return {0, u * u + 4.0 * dz * dz, t, u, e2, dz};
	}
	return {1, e2, t, u, e2, dz};
}

/// Janela da busca local de project(pos, near): metros para trás/frente de near.
const double kNearWindow = 50.0;
/// Mais longe que isso da amostra achada na janela = perdido (respawn): busca global.
const double kNearLost = 15.0;

/** Passo 1 com dica: amostra mais próxima (mesma nota de NearestSample) só nas amostras a até
 * kNearWindow metros de near. Mantém o carro no trecho em que estava quando dois trechos da pista
 * passam perto. Devolve -1 se a melhor ficar além de kNearLost. */
int NearestSampleNear(const TrackData &d, double x, double y, double z, bool hasZ, double near)
{
	const int n = d.count;
	const int c = Locate(d, near).i;
	const double step = (d.step > 1e-6) ? d.step : std::max(1e-3, d.length / std::max(1, n - 1));
	const int w = std::min(n / 2, int(std::ceil(kNearWindow / step)) + 1);
	double best = std::numeric_limits<double>::infinity();
	int bk = -1;
	for (int o = -w; o <= w; ++o) {
		int k = c + o;
		if (d.cyclic) {
			k = ((k % n) + n) % n;
		}
		else if (k < 0 || k >= n) {
			continue;
		}
		const double dx = d.px[k] - x, dy = d.py[k] - y;
		double m = dx * dx + dy * dy;
		if (hasZ) {
			const double dz = d.pz[k] - z;
			m += 4.0 * dz * dz;
		}
		if (m < best) {
			best = m;
			bk = k;
		}
	}
	return (best <= kNearLost * kNearLost) ? bk : -1;
}

Projection Project(const TrackData &d, const double pos[3], bool hasZ, const double *near = nullptr)
{
	const double x = pos[0], y = pos[1], z = pos[2];
	const int n = d.count;
	if (n == 1) {
		return {0.0, 0.0, 0.0, 0.0};
	}
	int k = near ? NearestSampleNear(d, x, y, z, hasZ, *near) : -1;
	if (k < 0) {
		k = NearestSample(d, x, y, z, hasZ);
	}
	/* Passo 2: segmentos k-2..k+1 (cíclica dá a volta; aberta só os que existem), sem repetir. */
	int segs[4];
	int nseg = 0;
	for (int i = k - 2; i <= k + 1; ++i) {
		int c = i;
		if (d.cyclic) {
			c = ((i % n) + n) % n;
		}
		else if (i < 0 || i > n - 2) {
			continue;
		}
		if (std::find(segs, segs + nseg, c) == segs + nseg) {
			segs[nseg++] = c;
		}
	}
	SegmentFit best = {0, 0.0, 0.0, 0.0, 0.0, 0.0};
	int bi = -1;
	for (int a = 0; a < nseg; ++a) {
		const SegmentFit f = SolveSegment(d, segs[a], x, y, z, hasZ);
		if (bi < 0 || f.BetterThan(best)) {
			best = f;
			bi = segs[a];
		}
	}
	double s = d.s[bi] + best.t * (SegmentEndS(d, bi) - d.s[bi]);
	if (d.cyclic && s >= d.length) {
		s -= d.length;
	}
	return {s, best.u, best.e2, best.dz};
}

/* -------------------------------------------------------------------- */
/* Leitura do JSON (formato v1) */

bool ReadArray(const cJSON *root, const char *key, int count, bool required, std::vector<double> &out,
               std::string &err)
{
	const cJSON *arr = cJSON_GetObjectItemCaseSensitive(root, key);
	if (!arr) {
		if (required) {
			err = std::string("missing array '") + key + "'";
			return false;
		}
		out.clear();
		return true;
	}
	if (!cJSON_IsArray(arr)) {
		err = std::string("'") + key + "' is not an array";
		return false;
	}
	out.clear();
	out.reserve(count);
	const cJSON *item;
	cJSON_ArrayForEach(item, arr) {
		if (!cJSON_IsNumber(item)) {
			err = std::string("'") + key + "' has a non-number item";
			return false;
		}
		out.push_back(item->valuedouble);
	}
	if ((int)out.size() != count) {
		err = std::string("'") + key + "' has " + std::to_string(out.size()) + " items, expected " +
		      std::to_string(count);
		return false;
	}
	return true;
}

std::shared_ptr<TrackData> ParseTrack(const char *json, const std::string &fallbackName, std::string &err)
{
	cJSON *root = cJSON_Parse(json);
	if (!root) {
		err = "invalid JSON";
		return nullptr;
	}
	std::unique_ptr<cJSON, void (*)(cJSON *)> guard(root, cJSON_Delete);
	if (!cJSON_IsObject(root)) {
		err = "JSON root is not an object";
		return nullptr;
	}

	auto d = std::make_shared<TrackData>();
	const cJSON *version = cJSON_GetObjectItemCaseSensitive(root, "version");
	if (cJSON_IsNumber(version) && version->valueint > 1) {
		CM_Warning("Range.track: '" << fallbackName << "' has format version " << version->valueint
		           << ", this engine reads version 1");
	}
	const cJSON *name = cJSON_GetObjectItemCaseSensitive(root, "name");
	d->name = (cJSON_IsString(name) && name->valuestring) ? name->valuestring : fallbackName;
	const cJSON *cyclic = cJSON_GetObjectItemCaseSensitive(root, "cyclic");
	d->cyclic = cJSON_IsTrue(cyclic) || (cJSON_IsNumber(cyclic) && cyclic->valuedouble != 0.0);
	const cJSON *step = cJSON_GetObjectItemCaseSensitive(root, "step");
	if (cJSON_IsNumber(step)) {
		d->step = step->valuedouble;
	}

	const cJSON *sArr = cJSON_GetObjectItemCaseSensitive(root, "s");
	if (!cJSON_IsArray(sArr)) {
		err = "missing array 's'";
		return nullptr;
	}
	const int n = cJSON_GetArraySize(sArr);
	const cJSON *count = cJSON_GetObjectItemCaseSensitive(root, "count");
	if (cJSON_IsNumber(count) && count->valueint != n) {
		err = "'count' (" + std::to_string(count->valueint) + ") differs from the size of 's' (" +
		      std::to_string(n) + ")";
		return nullptr;
	}
	if (n < 1) {
		err = "track has no samples";
		return nullptr;
	}
	d->count = n;

	/* Mesmos padrões de runtime.py: só "s" é obrigatório; array ausente = zeros, lateral ausente =
	 * (-ty, tx) sem normalizar (tx ausente conta como 1), "surface" fora do tamanho = zeros. */
	struct Field {
		const char *key;
		std::vector<double> *dst;
	} fields[] = {
		{"s", &d->s},       {"px", &d->px},     {"py", &d->py},   {"pz", &d->pz},   {"tx", &d->tx},
		{"ty", &d->ty},     {"tz", &d->tz},     {"lx", &d->lx},   {"ly", &d->ly},   {"bank", &d->bank},
		{"wl", &d->wl},     {"wr", &d->wr},     {"el", &d->el},   {"er", &d->er},   {"race", &d->race},
	};
	for (const Field &f : fields) {
		if (!ReadArray(root, f.key, n, strcmp(f.key, "s") == 0, *f.dst, err)) {
			return nullptr;
		}
	}
	const bool hasTx = cJSON_GetObjectItemCaseSensitive(root, "tx") != nullptr;
	const bool hasTy = cJSON_GetObjectItemCaseSensitive(root, "ty") != nullptr;
	for (std::vector<double> *v : {&d->px, &d->py, &d->pz, &d->tx, &d->ty, &d->tz, &d->bank, &d->wl, &d->wr,
	                               &d->el, &d->er, &d->race}) {
		if (v->empty()) {
			v->assign(n, 0.0);
		}
	}
	if (d->lx.empty()) {
		d->lx.assign(n, 0.0);
		for (int i = 0; i < n; ++i) {
			d->lx[i] = hasTy ? -d->ty[i] : -0.0;
		}
	}
	if (d->ly.empty()) {
		d->ly.assign(n, 1.0);
		for (int i = 0; i < n; ++i) {
			d->ly[i] = hasTx ? d->tx[i] : 1.0;
		}
	}

	const cJSON *surf = cJSON_GetObjectItemCaseSensitive(root, "surface");
	if (cJSON_IsArray(surf) && cJSON_GetArraySize(surf) == n) {
		const cJSON *item;
		cJSON_ArrayForEach(item, surf) {
			d->surface.push_back(cJSON_IsNumber(item) ? (int)item->valuedouble : 0);
		}
	}
	else {
		d->surface.assign(n, 0);
	}
	const cJSON *names = cJSON_GetObjectItemCaseSensitive(root, "surfaces");
	if (cJSON_IsArray(names)) {
		const cJSON *item;
		cJSON_ArrayForEach(item, names) {
			d->surfaces.push_back((cJSON_IsString(item) && item->valuestring) ? item->valuestring : "");
		}
	}

	const cJSON *length = cJSON_GetObjectItemCaseSensitive(root, "length");
	d->length = cJSON_IsNumber(length) ? length->valuedouble : d->s.back();
	if (d->length <= 0.0) {
		d->length = d->s.back();
	}

	BuildGrid(*d);
	return d;
}

/* -------------------------------------------------------------------- */
/* Cache por nome, lido dos Text do Main do jogo e dos arquivos do LibLoad */

struct TrackCache {
	std::vector<Main *> mains;
	std::map<std::string, std::shared_ptr<TrackData>> tracks;
};

TrackCache &Cache()
{
	static TrackCache cache;
	return cache;
}

std::vector<Main *> CurrentMains()
{
	if (KX_KetsjiEngine *engine = KX_GetActiveEngine()) {
		if (BL_Converter *converter = engine->GetConverter()) {
			return converter->GetMainList();
		}
	}
	if (G_MAIN) {
		return {G_MAIN};
	}
	return {};
}

/// Lista de arquivos mudou (LibLoad/LibFree): esquece o que foi lido.
void SyncCache()
{
	TrackCache &cache = Cache();
	std::vector<Main *> mains = CurrentMains();
	if (mains != cache.mains) {
		cache.tracks.clear();
		cache.mains.swap(mains);
	}
}

/// "Pista_4" de "TRACK_Pista_4.json", ou vazio se o Text não é de pista.
std::string TrackNameFromText(const char *textName)
{
	const size_t len = strlen(textName), pre = strlen(kTextPrefix), suf = strlen(kTextSuffix);
	if (len <= pre + suf || strncmp(textName, kTextPrefix, pre) != 0 ||
	    strcmp(textName + len - suf, kTextSuffix) != 0) {
		return "";
	}
	return std::string(textName + pre, len - pre - suf);
}

Text *FindTrackText(const std::string &name)
{
	for (Main *bmain : Cache().mains) {
		for (Text *text = (Text *)bmain->text.first; text; text = (Text *)text->id.next) {
			if (TrackNameFromText(text->id.name + 2) == name) {
				return text;
			}
		}
	}
	return nullptr;
}

/* -------------------------------------------------------------------- */
/* Tipo Python Range.track.Track */

struct KX_TrackObject {
	PyObject_HEAD
	std::shared_ptr<TrackData> *data;
};

PyTypeObject KX_Track_Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"Track",
	sizeof(KX_TrackObject),
};

PyObject *NewTrackObject(const std::shared_ptr<TrackData> &data)
{
	KX_TrackObject *self = PyObject_New(KX_TrackObject, &KX_Track_Type);
	if (!self) {
		return nullptr;
	}
	self->data = new std::shared_ptr<TrackData>(data);
	return (PyObject *)self;
}

void Track_dealloc(KX_TrackObject *self)
{
	delete self->data;
	PyObject_Del(self);
}

inline const TrackData &Data(PyObject *self)
{
	return **((KX_TrackObject *)self)->data;
}

PyObject *MakeVector(const double v[3])
{
	return PyObjectFrom(mt::vec3((float)v[0], (float)v[1], (float)v[2]));
}

/** Posição: mathutils.Vector ou sequência de números (x, y[, z]). hasZ = falso com só 2
 * componentes: a altura não entra na projeção (como runtime.py). */
bool ReadPos(PyObject *value, double out[3], bool &hasZ, const char *fn)
{
	out[2] = 0.0;
	if (VectorObject_Check(value)) {
		VectorObject *vec = (VectorObject *)value;
		if (BaseMath_ReadCallback(vec) == -1) {
			return false;
		}
		if (vec->size < 2) {
			PyErr_Format(PyExc_ValueError, "Track.%s(pos): vector needs at least 2 components", fn);
			return false;
		}
		hasZ = vec->size > 2;
		for (int i = 0; i < std::min(3, (int)vec->size); ++i) {
			out[i] = vec->vec[i];
		}
		return true;
	}
	PyObject *fast = PySequence_Fast(value, "");
	if (!fast) {
		PyErr_Clear();
		PyErr_Format(PyExc_TypeError, "Track.%s(pos): expected a Vector or a sequence of 3 numbers", fn);
		return false;
	}
	const Py_ssize_t n = PySequence_Fast_GET_SIZE(fast);
	if (n < 2) {
		Py_DECREF(fast);
		PyErr_Format(PyExc_ValueError, "Track.%s(pos): expected 3 numbers, got %d", fn, (int)n);
		return false;
	}
	hasZ = n > 2;
	for (Py_ssize_t i = 0; i < std::min<Py_ssize_t>(n, 3); ++i) {
		out[i] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(fast, i));
		if (out[i] == -1.0 && PyErr_Occurred()) {
			Py_DECREF(fast);
			return false;
		}
	}
	Py_DECREF(fast);
	return true;
}

bool ReadS(PyObject *value, double &s)
{
	s = PyFloat_AsDouble(value);
	return !(s == -1.0 && PyErr_Occurred());
}

PyObject *Track_project(PyObject *self, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"pos", "near", nullptr};
	PyObject *value, *nearObj = Py_None;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|O:project", (char **)kwlist, &value, &nearObj)) {
		return nullptr;
	}
	double pos[3];
	bool hasZ;
	if (!ReadPos(value, pos, hasZ, "project")) {
		return nullptr;
	}
	double near = 0.0;
	if (nearObj != Py_None && !ReadS(nearObj, near)) {
		return nullptr;
	}
	const Projection p = Project(Data(self), pos, hasZ, (nearObj != Py_None) ? &near : nullptr);
	return Py_BuildValue("(did)", p.s, (p.u >= 0.0) ? 1 : -1, std::fabs(p.u));
}

PyObject *Track_isOnRoad(PyObject *self, PyObject *value)
{
	double pos[3];
	bool hasZ;
	if (!ReadPos(value, pos, hasZ, "isOnRoad")) {
		return nullptr;
	}
	const TrackData &d = Data(self);
	const Projection p = Project(d, pos, hasZ);
	/* Pista aberta: passou do começo ou do fim. */
	if (!d.cyclic && p.e2 > 0.25) {
		Py_RETURN_FALSE;
	}
	const SamplePos sp = Locate(d, p.s);
	const double w = (p.u >= 0.0) ? Lerp(d.wl, sp) : Lerp(d.wr, sp);
	if (std::fabs(p.u) > w) {
		Py_RETURN_FALSE;
	}
	return PyBool_FromLong(!hasZ || std::fabs(p.dz) <= kHeightTol);
}

PyObject *Track_pointAt(PyObject *self, PyObject *value)
{
	double s, out[3];
	if (!ReadS(value, s)) {
		return nullptr;
	}
	const TrackData &d = Data(self);
	PointAt(d, Locate(d, s), out);
	return MakeVector(out);
}

PyObject *Track_tangentAt(PyObject *self, PyObject *value)
{
	double s, out[3];
	if (!ReadS(value, s)) {
		return nullptr;
	}
	const TrackData &d = Data(self);
	TangentAt(d, Locate(d, s), out);
	return MakeVector(out);
}

PyObject *Track_lateralAt(PyObject *self, PyObject *value)
{
	double s, lat[2];
	if (!ReadS(value, s)) {
		return nullptr;
	}
	const TrackData &d = Data(self);
	LateralAt(d, Locate(d, s), lat);
	const double out[3] = {lat[0], lat[1], 0.0};
	return MakeVector(out);
}

PyObject *Track_bankAt(PyObject *self, PyObject *value)
{
	double s;
	if (!ReadS(value, s)) {
		return nullptr;
	}
	const TrackData &d = Data(self);
	return PyFloat_FromDouble(Lerp(d.bank, Locate(d, s)));
}

PyObject *Track_widthAt(PyObject *self, PyObject *value)
{
	double s;
	if (!ReadS(value, s)) {
		return nullptr;
	}
	const TrackData &d = Data(self);
	const SamplePos p = Locate(d, s);
	return Py_BuildValue("(dd)", Lerp(d.wl, p), Lerp(d.wr, p));
}

PyObject *Track_edgeAt(PyObject *self, PyObject *value)
{
	double s;
	if (!ReadS(value, s)) {
		return nullptr;
	}
	const TrackData &d = Data(self);
	const SamplePos p = Locate(d, s);
	return Py_BuildValue("(dd)", Lerp(d.el, p), Lerp(d.er, p));
}

PyObject *Track_racingLine(PyObject *self, PyObject *value)
{
	double s, c[3], lat[2];
	if (!ReadS(value, s)) {
		return nullptr;
	}
	const TrackData &d = Data(self);
	const SamplePos p = Locate(d, s);
	PointAt(d, p, c);
	LateralAt(d, p, lat);
	const double off = Lerp(d.race, p);
	const double out[3] = {c[0] + lat[0] * off, c[1] + lat[1] * off, c[2] - off * std::tan(Lerp(d.bank, p))};
	return MakeVector(out);
}

PyObject *Track_surfaceAt(PyObject *self, PyObject *value)
{
	double s;
	if (!ReadS(value, s)) {
		return nullptr;
	}
	const TrackData &d = Data(self);
	const SamplePos p = Locate(d, s);
	const int id = d.surface[p.i];
	if (id >= 0 && id < (int)d.surfaces.size()) {
		return PyUnicode_FromString(d.surfaces[id].c_str());
	}
	return PyUnicode_FromString("");
}

PyObject *Track_get_name(PyObject *self, void *)
{
	return PyUnicode_FromString(Data(self).name.c_str());
}

PyObject *Track_get_length(PyObject *self, void *)
{
	return PyFloat_FromDouble(Data(self).length);
}

PyObject *Track_get_cyclic(PyObject *self, void *)
{
	return PyBool_FromLong(Data(self).cyclic);
}

PyObject *Track_get_count(PyObject *self, void *)
{
	return PyLong_FromLong(Data(self).count);
}

PyObject *Track_get_surfaces(PyObject *self, void *)
{
	const TrackData &d = Data(self);
	PyObject *list = PyList_New(d.surfaces.size());
	for (size_t i = 0; i < d.surfaces.size(); ++i) {
		PyList_SET_ITEM(list, i, PyUnicode_FromString(d.surfaces[i].c_str()));
	}
	return list;
}

PyObject *Track_repr(PyObject *self)
{
	const TrackData &d = Data(self);
	return PyUnicode_FromFormat("<Track '%s', %d samples, %s>", d.name.c_str(), d.count,
	                            std::to_string(d.length).c_str());
}

PyMethodDef Track_methods[] = {
	{"project", (PyCFunction)Track_project, METH_VARARGS | METH_KEYWORDS,
	 "project(pos, near=None) -> (s, side, dist): meters along the track at the projected point, side +1 "
	 "left / -1 right and lateral distance from the center line. With z, height picks the right level on "
	 "bridges and crossings. near = the s of the previous frame: searches 50 m around it so the car never "
	 "jumps to a nearby stretch of the track (falls back to the whole track when more than 15 m away)."},
	{"pointAt", (PyCFunction)Track_pointAt, METH_O, "pointAt(s) -> Vector: center line point at s meters."},
	{"tangentAt", (PyCFunction)Track_tangentAt, METH_O, "tangentAt(s) -> Vector: unit 3D direction at s."},
	{"lateralAt", (PyCFunction)Track_lateralAt, METH_O,
	 "lateralAt(s) -> Vector: horizontal unit vector to the left at s."},
	{"bankAt", (PyCFunction)Track_bankAt, METH_O, "bankAt(s) -> float: banking in radians (+ = drops to the left)."},
	{"widthAt", (PyCFunction)Track_widthAt, METH_O, "widthAt(s) -> (left, right): asphalt half widths."},
	{"edgeAt", (PyCFunction)Track_edgeAt, METH_O,
	 "edgeAt(s) -> (left, right): lateral offset of the border band (wall, guard rail)."},
	{"racingLine", (PyCFunction)Track_racingLine, METH_O, "racingLine(s) -> Vector: racing line point at s."},
	{"isOnRoad", (PyCFunction)Track_isOnRoad, METH_O, "isOnRoad(pos) -> bool: pos is over the asphalt (inside the half widths) and up to 3 m from the "
	 "surface."},
	{"surfaceAt", (PyCFunction)Track_surfaceAt, METH_O, "surfaceAt(s) -> str: surface name at s."},
	{nullptr, nullptr, 0, nullptr}
};

PyGetSetDef Track_getset[] = {
	{"name", (getter)Track_get_name, nullptr, "Track name (str).", nullptr},
	{"length", (getter)Track_get_length, nullptr, "Track length in meters (float).", nullptr},
	{"cyclic", (getter)Track_get_cyclic, nullptr, "True for a closed circuit (s wraps around).", nullptr},
	{"count", (getter)Track_get_count, nullptr, "Number of baked samples (int).", nullptr},
	{"surfaces", (getter)Track_get_surfaces, nullptr, "Surface names (list of str).", nullptr},
	{nullptr, nullptr, nullptr, nullptr, nullptr}
};

/* -------------------------------------------------------------------- */
/* Funções do módulo */

PyObject *gPyTrackGet(PyObject *, PyObject *value)
{
	if (!PyUnicode_Check(value)) {
		PyErr_SetString(PyExc_TypeError, "Range.track.get(name): name must be a str");
		return nullptr;
	}
	std::string name = _PyUnicode_AsString(value);
	/* Aceita também o nome do Text ("TRACK_Pista_4.json"). */
	const std::string fromText = TrackNameFromText(name.c_str());
	if (!fromText.empty()) {
		name = fromText;
	}

	SyncCache();
	TrackCache &cache = Cache();
	auto it = cache.tracks.find(name);
	if (it != cache.tracks.end()) {
		return NewTrackObject(it->second);
	}
	Text *text = FindTrackText(name);
	if (!text) {
		Py_RETURN_NONE;
	}
	char *buf = txt_to_buf(text);
	std::string err;
	std::shared_ptr<TrackData> data = ParseTrack(buf ? buf : "", name, err);
	if (buf) {
		MEM_freeN(buf);
	}
	if (!data) {
		PyErr_Format(PyExc_ValueError, "Range.track.get(): Text '%s': %s", text->id.name + 2, err.c_str());
		return nullptr;
	}
	cache.tracks[name] = data;
	return NewTrackObject(data);
}

PyObject *gPyTrackNames(PyObject *, PyObject *)
{
	SyncCache();
	std::vector<std::string> names;
	for (Main *bmain : Cache().mains) {
		for (Text *text = (Text *)bmain->text.first; text; text = (Text *)text->id.next) {
			const std::string n = TrackNameFromText(text->id.name + 2);
			if (!n.empty() && std::find(names.begin(), names.end(), n) == names.end()) {
				names.push_back(n);
			}
		}
	}
	PyObject *list = PyList_New(names.size());
	for (size_t i = 0; i < names.size(); ++i) {
		PyList_SET_ITEM(list, i, PyUnicode_FromString(names[i].c_str()));
	}
	return list;
}

PyObject *gPyTrackFromJson(PyObject *, PyObject *args)
{
	const char *json;
	const char *name = "";
	if (!PyArg_ParseTuple(args, "s|s:fromJson", &json, &name)) {
		return nullptr;
	}
	std::string err;
	std::shared_ptr<TrackData> data = ParseTrack(json, name, err);
	if (!data) {
		PyErr_Format(PyExc_ValueError, "Range.track.fromJson(): %s", err.c_str());
		return nullptr;
	}
	return NewTrackObject(data);
}

PyObject *gPyTrackReload(PyObject *, PyObject *)
{
	KX_TrackClearCache();
	Py_RETURN_NONE;
}

PyMethodDef track_methods[] = {
	{"get", (PyCFunction)gPyTrackGet, METH_O,
	 "get(name) -> Track or None: track baked in the Text 'TRACK_<name>.json' of the game file (or of a "
	 "LibLoaded file). Read once and cached."},
	{"names", (PyCFunction)gPyTrackNames, METH_NOARGS, "names() -> list of str: tracks available in the loaded files."},
	{"fromJson", (PyCFunction)gPyTrackFromJson, METH_VARARGS,
	 "fromJson(text, name='') -> Track: track from a JSON string in the baked format (version 1)."},
	{"reload", (PyCFunction)gPyTrackReload, METH_NOARGS,
	 "reload(): forget the cached tracks; the next get() reads the Text again."},
	{nullptr, nullptr, 0, nullptr}
};

PyDoc_STRVAR(track_module_doc,
"Range.track: baked track data of the Track Tool (Text 'TRACK_<name>.json').\n"
"get(name) returns a Track with project(pos), pointAt(s), tangentAt(s), bankAt(s), widthAt(s),\n"
"racingLine(s), isOnRoad(pos), surfaceAt(s), length and name.");

PyModuleDef track_module_def = {
	PyModuleDef_HEAD_INIT,
	"Range.track",
	track_module_doc,
	0,
	track_methods,
	nullptr,
	nullptr,
	nullptr,
	nullptr,
};

}  // namespace

void KX_TrackClearCache()
{
	TrackCache &cache = Cache();
	cache.tracks.clear();
	cache.mains.clear();
}

PyMODINIT_FUNC initTrackPythonBinding()
{
	KX_Track_Type.tp_dealloc = (destructor)Track_dealloc;
	KX_Track_Type.tp_flags = Py_TPFLAGS_DEFAULT;
	KX_Track_Type.tp_doc = "Baked track of the Track Tool; get one with Range.track.get(name).";
	KX_Track_Type.tp_methods = Track_methods;
	KX_Track_Type.tp_getset = Track_getset;
	KX_Track_Type.tp_repr = (reprfunc)Track_repr;
	if (PyType_Ready(&KX_Track_Type) < 0) {
		return nullptr;
	}
	PyObject *module = PyModule_Create(&track_module_def);
	if (!module) {
		return nullptr;
	}
	Py_INCREF(&KX_Track_Type);
	PyModule_AddObject(module, "Track", (PyObject *)&KX_Track_Type);
	return module;
}

#else  // WITH_PYTHON

void KX_TrackClearCache()
{
}

#endif  // WITH_PYTHON
