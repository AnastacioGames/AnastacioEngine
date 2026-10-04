/*******************************************************************************
 * Anastacio Engine: saida de audio do runtime Web via AudioWorklet.
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
 * @file WebAudioDevice.h
 * @ingroup plugin
 * The WebAudioDevice class.
 *
 * Substitui o SDLDevice no navegador: o port SDL2 do Emscripten toca por
 * ScriptProcessorNode, API obsoleta. Aqui um AudioWorkletNode recebe blocos ja
 * mixados pela thread principal (mesmo modelo de thread do ScriptProcessor, sem
 * SharedArrayBuffer, logo sem exigir COOP/COEP do servidor).
 */

#include "devices/SoftwareDevice.h"

#include <vector>

AUD_NAMESPACE_BEGIN

class AUD_PLUGIN_API WebAudioDevice : public SoftwareDevice
{
private:
	/// Whether there is currently playback.
	bool m_playback;

	/// Id do dispositivo no lado JavaScript.
	int m_id;

	/// Bloco mixado entregue ao JavaScript (float32 intercalado).
	std::vector<float> m_buffer;

	// delete copy constructor and operator=
	WebAudioDevice(const WebAudioDevice&) = delete;
	WebAudioDevice& operator=(const WebAudioDevice&) = delete;

protected:
	virtual void playing(bool playing);

public:
	/**
	 * Abre a saida Web Audio. Nao lanca excecao (o runtime Web nao captura):
	 * so e registrado quando o navegador suporta AudioWorklet.
	 * \param specs The wanted audio specification.
	 * \param buffersize Frames por bloco pedido pelo AudioWorklet.
	 */
	WebAudioDevice(DeviceSpecs specs, int buffersize = AUD_DEFAULT_BUFFER_SIZE);

	virtual ~WebAudioDevice();

	/**
	 * Mixa frames no bloco interno e devolve seu endereco (chamado pelo JavaScript).
	 */
	float* mixBlock(int frames);

	/**
	 * Registers this plugin when the browser supports AudioWorklet.
	 */
	static void registerPlugin();
};

AUD_NAMESPACE_END
