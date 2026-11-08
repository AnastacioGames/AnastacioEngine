/*******************************************************************************
 * Anastacio Engine: interface dos backends de captura de microfone.
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
 * @file IMicrophoneBackend.h
 * @ingroup devices
 * Backend de captura usado por aud::Microphone (OpenAL no desktop, WebAudio na
 * Web, "Test" para testes sem microfone). Ver docs/plano-microfone.md.
 */

#include "respec/Specification.h"

#include <memory>
#include <string>
#include <vector>

AUD_NAMESPACE_BEGIN

/// Estado da captura, igual em todas as plataformas.
enum MicrophoneState
{
	MICROPHONE_STATE_CLOSED  = 0, /// Parado.
	MICROPHONE_STATE_PENDING = 1, /// Esperando permissao (Web/Android).
	MICROPHONE_STATE_GRANTED = 2, /// Capturando.
	MICROPHONE_STATE_DENIED  = 3, /// Permissao negada.
	MICROPHONE_STATE_ERROR   = 4  /// Sem dispositivo ou falha ao abrir.
};

/// Uma captura aberta.
class AUD_API IMicrophoneBackend
{
public:
	virtual ~IMicrophoneBackend() {}

	/// Taxa e canais reais (podem diferir do pedido, ex.: Web usa a taxa do AudioContext).
	virtual Specs getSpecs() const = 0;

	virtual MicrophoneState getState() const = 0;

	/// Frames prontos para leitura agora.
	virtual int available() = 0;

	/// Frames que o backend segura antes de perder amostras.
	virtual int capacity() const = 0;

	/// Le frames float intercalados; frames <= available().
	virtual void read(int frames, sample_t* buffer) = 0;
};

/// Fabrica registrada por cada plugin em Microphone::registerBackend.
class AUD_API IMicrophoneBackendFactory
{
public:
	virtual ~IMicrophoneBackendFactory() {}

	/// Maior prioridade vence quando nenhum backend e pedido pelo nome.
	virtual int getPriority() = 0;

	virtual std::vector<std::string> getDeviceNames() = 0;

	/**
	 * Abre a captura. device vazio = padrao do sistema.
	 * Lanca DeviceException se nao der para abrir.
	 */
	virtual std::shared_ptr<IMicrophoneBackend> open(const std::string& device, Specs specs, int capacity_frames) = 0;
};

AUD_NAMESPACE_END
