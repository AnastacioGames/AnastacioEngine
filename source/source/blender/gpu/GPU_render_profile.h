/* Optional main-render-thread diagnostics. No logic/physics clocks are changed. */
#ifndef __GPU_RENDER_PROFILE_H__
#define __GPU_RENDER_PROFILE_H__

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
	GPU_RENDER_OBJECT,
	GPU_RENDER_SHADOW,
	GPU_RENDER_LIGHTS,
	GPU_RENDER_PROBES,
	GPU_RENDER_DAMAGE,
	GPU_RENDER_SKINNING,
	GPU_RENDER_PHASE_TOT
};
enum {
	GPU_RENDER_FLOAT1,
	GPU_RENDER_FLOAT2,
	GPU_RENDER_FLOAT3,
	GPU_RENDER_FLOAT4,
	GPU_RENDER_MATRIX3,
	GPU_RENDER_MATRIX4,
	GPU_RENDER_INTEGER,
	GPU_RENDER_SAMPLER,
	GPU_RENDER_MUL,
	GPU_RENDER_INVERSE,
	GPU_RENDER_KIND_TOT
};

#ifdef _MSC_VER
#define GPU_RENDER_THREAD_LOCAL __declspec(thread)
#else
#define GPU_RENDER_THREAD_LOCAL __thread
#endif

extern bool GPU_render_profile_enabled;
extern GPU_RENDER_THREAD_LOCAL int GPU_render_profile_phase;
extern unsigned long long GPU_render_profile_calls[GPU_RENDER_PHASE_TOT];
extern unsigned long long GPU_render_profile_counts[GPU_RENDER_PHASE_TOT][GPU_RENDER_KIND_TOT];

static inline void GPU_render_profile_count(int kind)
{
	if (GPU_render_profile_enabled && GPU_render_profile_phase >= 0) {
		GPU_render_profile_counts[GPU_render_profile_phase][kind]++;
	}
}

#ifdef __cplusplus
}

/* Restore the caller's phase on every return. Used only on the render thread. */
class GPU_RenderProfileScope {
	int m_previous;
	bool m_active;
public:
	explicit GPU_RenderProfileScope(int phase)
		: m_previous(-1), m_active(GPU_render_profile_enabled)
	{
		if (m_active) {
			m_previous = GPU_render_profile_phase;
			GPU_render_profile_phase = phase;
			GPU_render_profile_calls[phase]++;
		}
	}
	~GPU_RenderProfileScope()
	{
		if (m_active) {
			GPU_render_profile_phase = m_previous;
		}
	}
};
#endif
#endif
