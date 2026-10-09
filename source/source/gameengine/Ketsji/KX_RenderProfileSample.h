/* CPU sampling for frequently repeated render calls; no GPU timestamps. */
#ifndef __KX_RENDER_PROFILE_SAMPLE_H__
#define __KX_RENDER_PROFILE_SAMPLE_H__
#include "KX_EngineProfiler.h"
namespace KX_EngineProfiler {
class RenderSample {
 int m_id;
 double m_start;
public:
 RenderSample(int id, unsigned int& counter) : m_id(id), m_start(0.0) {
  // 61 is coprime with the benchmark object counts and avoids fixed mesh aliasing.
  if (Enabled() && ++counter % 61 == 0) m_start = NowMs();
 }
 ~RenderSample() {
  if (m_start != 0.0 && Enabled()) AddCpu(m_id, (NowMs() - m_start) * 61.0);
 }
};
}
#define RANGE_RENDER_SAMPLE(name) \
 static const int RANGE_PROFILE_CAT(renderSampleId, __LINE__) = KX_EngineProfiler::Register(name); \
 static unsigned int RANGE_PROFILE_CAT(renderSampleCount, __LINE__) = (RANGE_PROFILE_CAT(renderSampleId, __LINE__) * 13) % 61; \
 KX_EngineProfiler::RenderSample RANGE_PROFILE_CAT(renderSample, __LINE__)( \
 RANGE_PROFILE_CAT(renderSampleId, __LINE__), RANGE_PROFILE_CAT(renderSampleCount, __LINE__))
#endif
