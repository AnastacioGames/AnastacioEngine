/*******************************************************************************
 * Anastacio Engine: efeitos de voz (presets).
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
 * @file VoiceFX.h
 * @ingroup fx
 * Presets de efeito de voz, corte/fade/normalizar e pico de um som.
 * Mesma tabela para editor, bricks, nós e Range.audio.
 */

#include "ISound.h"

#include <memory>
#include <string>
#include <vector>

AUD_NAMESPACE_BEGIN

class AUD_API VoiceFX
{
public:
	/// Nomes dos presets, na ordem da UI ("NONE" primeiro).
	static std::vector<std::string> presetNames();

	/// true se o preset não serve para som ao vivo (ex.: REVERSE).
	static bool needsRecorded(const std::string& preset);

	/**
	 * Aplica o preset. amount 0..1 (0 = sem efeito, 1 = efeito cheio).
	 * Lança Exception para preset desconhecido.
	 */
	static std::shared_ptr<ISound> apply(std::shared_ptr<ISound> sound, const std::string& preset, float amount = 1.0f);

	/// Maior amostra absoluta (lê até max_seconds do som).
	static float peak(std::shared_ptr<ISound> sound, float max_seconds = 600.0f);

	/// Duração em segundos (negativo se desconhecida/infinita).
	static float duration(std::shared_ptr<ISound> sound);

	/**
	 * Corte não destrutivo: start/end em segundos (end < 0 = até o fim),
	 * fades em segundos e normalização pelo pico (alvo 0.95).
	 */
	static std::shared_ptr<ISound> edit(std::shared_ptr<ISound> sound, float start = 0.0f, float end = -1.0f,
	                                    float fade_in = 0.0f, float fade_out = 0.0f, bool normalize = false);

	/// Grava o som em WAV PCM 16 bits (writer próprio, funciona na Web). Lança FileException.
	static void saveWAV(std::shared_ptr<ISound> sound, const std::string& path, float max_seconds = 600.0f);
};

AUD_NAMESPACE_END
