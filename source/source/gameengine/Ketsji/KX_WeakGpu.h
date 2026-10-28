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

/** \file KX_WeakGpu.h
 *  \ingroup ketsji
 *  \brief Weak PC simulator (docs/weak-pc-simulator.md).
 *
 * RANGE_WEAK_GPU=<factor> (e.g. 4) makes the GPU behave about `factor` times slower: each frame
 * its GPU time is measured with timestamps and (factor - 1) times that is spent in a dummy
 * fullscreen pass, so GPU Latency, the frame rate and dynamic resolution react as on a weaker
 * card. The pass costs the same per pixel everywhere, so the proportions between effects stay
 * those of this card; only the total is scaled. It also reports the GPU as integrated (Auto = Low).
 */

#ifndef __KX_WEAKGPU_H__
#define __KX_WEAKGPU_H__

class RAS_Rasterizer;
struct GPUShader;

class KX_WeakGpu
{
public:
	/// Factor from RANGE_WEAK_GPU, 0 when off (unset, < 1.01 or not a number).
	static float EnvFactor();

	KX_WeakGpu(float factor);
	~KX_WeakGpu();

	/// After the frame's first GL work: stamps its start and reads a finished frame back.
	void FrameStart();
	/// End of the frame's rendering: stamps it and spends the extra GPU time.
	void Burn(RAS_Rasterizer *rasterizer);

	float GetFactor() const
	{
		return m_factor;
	}

private:
	static const int frames = 3;

	float m_factor;
	bool m_init;
	bool m_supported;
	GPUShader *m_shader;
	int m_iterationsLoc;
	unsigned int m_queries[frames][3];
	bool m_pending[frames];
	int m_current;
	bool m_started;
	/// Shader loop iterations per pixel over all passes, adjusted to hit the target time.
	float m_iterations;

	void Init();
};

#endif  // __KX_WEAKGPU_H__
