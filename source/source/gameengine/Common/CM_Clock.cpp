#include "CM_Clock.h"

CM_Clock::CM_Clock()
	:m_manual(false),
	m_manualTimeSecond(0.0)
{
	Reset();
}

void CM_Clock::Reset()
{
	m_manual = false;
	m_start = m_clock.now();
}

double CM_Clock::GetTimeSecond() const
{
	if (m_manual) {
		return m_manualTimeSecond;
	}
	return GetTimeNano() * 1e-9;
}

CM_Clock::Rep CM_Clock::GetTimeNano() const
{
	if (m_manual) {
		return (Rep)(m_manualTimeSecond * 1e9);
	}
	const std::chrono::high_resolution_clock::time_point now = m_clock.now();
	return std::chrono::duration_cast<std::chrono::nanoseconds>(now - m_start).count();
}

void CM_Clock::SetManualTime(double timeSecond)
{
	m_manual = true;
	m_manualTimeSecond = timeSecond;
}

void CM_Clock::AdvanceManualTime(double deltaSecond)
{
	m_manual = true;
	m_manualTimeSecond += deltaSecond;
}