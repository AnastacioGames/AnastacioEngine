#ifndef __CM_CLOCK_H__
#define __CM_CLOCK_H__

#include <chrono>

class CM_Clock
{
public:
	using Rep = std::chrono::nanoseconds::rep;

private:
	std::chrono::high_resolution_clock::time_point m_start;
	std::chrono::high_resolution_clock m_clock;

	/** Testing-only override: when set (SetManualTime/AdvanceManualTime), GetTimeSecond()/
	 * GetTimeNano() return this value instead of reading the real hardware clock. Lets tests
	 * of frame timing (KX_KetsjiEngine::ClockTiming, KX_TimeCategoryLogger) be deterministic.
	 * See docs/ketsji-engine-modernization-plan.md, Plano 3.
	 */
	bool m_manual;
	double m_manualTimeSecond;

public:
	CM_Clock();

	void Reset();

	double GetTimeSecond() const;
	Rep GetTimeNano() const;

	void SetManualTime(double timeSecond);
	void AdvanceManualTime(double deltaSecond);
};

#endif  // __CM_CLOCK_H__
