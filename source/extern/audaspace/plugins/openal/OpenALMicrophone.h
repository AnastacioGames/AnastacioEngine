/*******************************************************************************
 * Anastacio Engine: captura de microfone por OpenAL (desktop).
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
 * @file OpenALMicrophone.h
 * @ingroup plugin
 * Fabrica do backend "OpenAL" de aud::Microphone (alcCapture*).
 */

#include "devices/IMicrophoneBackend.h"

AUD_NAMESPACE_BEGIN

class AUD_PLUGIN_API OpenALMicrophone : public IMicrophoneBackendFactory
{
public:
	int getPriority() override;
	std::vector<std::string> getDeviceNames() override;
	std::shared_ptr<IMicrophoneBackend> open(const std::string& device, Specs specs, int capacity_frames) override;

	/// Registra o backend em Microphone (chamado pelo PluginManager).
	static void registerPlugin();
};

AUD_NAMESPACE_END
