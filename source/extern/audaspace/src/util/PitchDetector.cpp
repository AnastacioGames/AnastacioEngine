/*******************************************************************************
 * Anastacio Engine: deteccao de altura (nota) de uma voz ou instrumento.
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

#include "util/PitchDetector.h"

#include <algorithm>
#include <cmath>

namespace aud {

PitchResult PitchDetector::detect(const float* samples, int count, float rate, float min_hz,
                                  float max_hz, float threshold, float min_rms)
{
	const PitchResult none = {0.0f, 0.0f};
	const int tau_min = std::max(2, int(rate / max_hz));
	const int tau_max = int(std::ceil(rate / min_hz));
	if(count < 2 * tau_max || tau_min + 1 >= tau_max)
		return none;

	double energy = 0.0;
	for(int i = 0; i < count; i++)
		energy += samples[i] * samples[i];
	if(std::sqrt(energy / count) < min_rms)
		return none;

	const int window = count - tau_max;
	m_cmnd.resize(tau_max + 2);
	m_cmnd[0] = 1.0f;

	/* Diferenca ao quadrado normalizada pela media acumulada (passos 2 e 3 do YIN). */
	double sum = 0.0;
	for(int tau = 1; tau <= tau_max + 1 && tau + window <= count; tau++)
	{
		double difference = 0.0;
		for(int i = 0; i < window; i++)
		{
			const float delta = samples[i] - samples[i + tau];
			difference += delta * delta;
		}
		sum += difference;
		m_cmnd[tau] = sum > 0.0 ? float(difference * tau / sum) : 1.0f;
	}

	/* Primeiro vale abaixo do limite: pegar o menor global causaria erro de oitava. */
	const int last = std::min(tau_max, count - window - 1);
	int best = -1;
	for(int tau = tau_min; tau <= last; tau++)
	{
		if(m_cmnd[tau] < threshold)
		{
			while(tau < last && m_cmnd[tau + 1] < m_cmnd[tau])
				tau++;
			best = tau;
			break;
		}
	}
	if(best < 0)
		return none;

	/* Parabola no vale: acha o periodo entre duas amostras. */
	double period = best;
	const double a = m_cmnd[best - 1], b = m_cmnd[best], c = m_cmnd[best + 1];
	const double curve = a - 2.0 * b + c;
	if(curve > 0.0)
		period += 0.5 * (a - c) / curve;

	PitchResult result;
	result.frequency = float(rate / period);
	result.confidence = std::max(0.0f, 1.0f - m_cmnd[best]);
	return result;
}

NoteResult PitchDetector::note(float frequency, float a4)
{
	const double exact = 69.0 + 12.0 * std::log2(frequency / a4);
	NoteResult result;
	result.midi = int(std::lround(exact));
	result.cents = float((exact - result.midi) * 100.0);
	return result;
}

}
