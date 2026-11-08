/*******************************************************************************
 * Anastacio Engine: captura de microfone.
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
 * @file Microphone.h
 * @ingroup devices
 * Captura de microfone igual em todas as plataformas.
 *
 * poll() puxa o que o backend tem para uma fila circular (~2 s), mede nivel e
 * pico e acumula a gravacao. Cada som ao vivo (createLiveSound) tem seu proprio
 * cursor nessa fila, entao nivel, gravacao e sons ao vivo nao disputam amostras.
 * Os sons ao vivo tambem chamam poll() quando faltam dados, entao tocam mesmo
 * sem um laco chamando poll(). Tudo protegido por um mutex.
 */

#include "devices/IMicrophoneBackend.h"

#include <cstdint>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

AUD_NAMESPACE_BEGIN

class ISound;

class AUD_API Microphone : public std::enable_shared_from_this<Microphone>
{
private:
	std::string m_device;
	std::string m_backend_name;
	Specs m_requested;
	Specs m_specs;
	float m_seconds;

	std::shared_ptr<IMicrophoneBackend> m_backend;
	MicrophoneState m_state;
	std::string m_error;

	/// Fila circular de frames float intercalados.
	std::vector<sample_t> m_ring;
	int m_ring_frames;
	/// Total de frames ja escritos na fila (posicao absoluta).
	uint64_t m_written;

	std::vector<sample_t> m_temp;

	float m_level;
	float m_peak;
	int m_dropped;

	bool m_recording;
	std::vector<sample_t> m_record;
	std::shared_ptr<ISound> m_last_recording;
	Specs m_last_recording_specs;

	mutable std::recursive_mutex m_mutex;

	static std::map<std::string, std::shared_ptr<IMicrophoneBackendFactory>>& registry();

	void pollLocked();

	Microphone(const Microphone&) = delete;
	Microphone& operator=(const Microphone&) = delete;

public:
	/**
	 * \param device Nome do dispositivo; vazio = padrao.
	 * \param specs Taxa/canais pedidos (mono ou estereo). A taxa real vem em getSpecs().
	 * \param backend Nome do backend ("OpenAL", "WebAudio", "Test"); vazio = maior prioridade.
	 * \param seconds Tamanho da fila circular.
	 */
	Microphone(const std::string& device = "", Specs specs = {RATE_22050, CHANNELS_MONO},
	           const std::string& backend = "", float seconds = 2.0f);
	~Microphone();

	static void registerBackend(const std::string& name, std::shared_ptr<IMicrophoneBackendFactory> factory);
	static std::vector<std::string> getBackendNames();
	/// Dispositivos do backend pedido (ou do de maior prioridade).
	static std::vector<std::string> getDeviceNames(const std::string& backend = "");

	/// Abre o backend. Em erro fica em MICROPHONE_STATE_ERROR e devolve false (ver getError()).
	bool start();
	void stop();
	bool isActive() const;

	/// Puxa as amostras novas do backend. Seguro em qualquer thread.
	void poll();

	MicrophoneState getState() const;
	std::string getError() const;
	std::string getBackendName() const;
	Specs getSpecs() const;

	/// RMS do ultimo bloco lido (0..1).
	float getLevel() const;
	/// Pico com queda suave (0..1).
	float getPeak() const;
	/// Quantas vezes houve perda de amostras (fila do backend cheia ou leitor atrasado).
	int getDropped() const;

	void startRecording();
	/// Para a gravacao e devolve o som gravado (tambem guardado em getLastRecording()).
	std::shared_ptr<ISound> stopRecording();
	bool isRecording() const;
	float getRecordingSeconds() const;
	std::shared_ptr<ISound> getLastRecording() const;

	/// Som que toca o microfone ao vivo; completa com silencio quando faltam dados.
	std::shared_ptr<ISound> createLiveSound();

	/// Usado pelo leitor ao vivo: copia frames a partir de cursor; devolve frames copiados.
	int readFrom(uint64_t& cursor, int frames, sample_t* buffer);
	/// Posicao inicial de um leitor ao vivo novo (um pouco atras do fim, para nao faltar dado).
	uint64_t liveStartPosition();

	/// Grava a ultima gravacao em WAV PCM 16 bits. Lanca FileException em erro.
	void saveWAV(const std::string& path) const;

	/// Grava frames float intercalados em WAV PCM 16 bits. Lanca FileException em erro.
	static void writeWAV(const std::string& path, const sample_t* data, int frames, Specs specs);
};

AUD_NAMESPACE_END
