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

#pragma once

/**
 * @file PitchDetector.h
 * @ingroup util
 * YIN (de Cheveigne e Kawahara, 2002): uma nota por vez, sem dependencias.
 */

#include <vector>

namespace aud {

struct PitchResult
{
	/// Frequencia em Hz; 0 quando nao ha nota clara (silencio, ruido).
	float frequency;
	/// 0..1: o quanto o trecho e periodico.
	float confidence;
};

struct NoteResult
{
	/// Numero MIDI da nota mais proxima (69 = A4).
	int midi;
	/// Desvio dessa nota, em cents (-50..50).
	float cents;
};

class PitchDetector
{
	std::vector<float> m_cmnd;

public:
	/**
	 * \param samples Audio mono; precisa de pelo menos 2 * rate / min_hz amostras.
	 * \param threshold Limite do YIN: menor = mais exigente.
	 * \param min_rms Abaixo desse volume o trecho conta como silencio.
	 */
	PitchResult detect(const float* samples, int count, float rate, float min_hz = 70.0f,
	                   float max_hz = 1600.0f, float threshold = 0.15f, float min_rms = 0.005f);

	static NoteResult note(float frequency, float a4 = 440.0f);
};

}
