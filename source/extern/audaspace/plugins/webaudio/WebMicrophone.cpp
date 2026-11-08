/*******************************************************************************
 * Anastacio Engine: microfone no runtime Web.
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

#include "WebMicrophone.h"
#include "Exception.h"
#include "devices/Microphone.h"

#include <emscripten.h>

#include <algorithm>
#include <vector>

/* Fluxo: getUserMedia -> MediaStreamSource -> AudioWorklet 'range-input', no mesmo AudioContext
 * da saida (Module.rangeAudio.ctx). O worklet manda blocos Float32Array mono pela porta; a thread
 * principal copia para o heap e chama _aud_webmic_push, que escreve na fila do backend.
 * O no tem uma saida ligada a um GainNode com ganho 0, senao alguns navegadores nao chamam process().
 * Pagina oculta: os blocos sao descartados (nivel 0, sem erro). Estado em Module.rangeMic. */

EM_JS(int, aud_webmic_supported, (), {
	if (typeof navigator === 'undefined' || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return 0;
	if (typeof AudioWorkletNode === 'undefined') return 0;
	if (typeof isSecureContext !== 'undefined' && !isSecureContext) return 0;
	return 1;
});

EM_JS(int, aud_webmic_rate, (), {
	var A = Module.rangeAudio;
	return A && A.ctx ? A.ctx.sampleRate : 0;
});

/* Estados: 1 pendente, 2 liberado, 3 negado, 4 erro (igual a aud::MicrophoneState). */
EM_JS(int, aud_webmic_open, (void* backend), {
	var A = Module.rangeAudio;
	if (!A || !A.ctx || !A.ctx.audioWorklet) return 0;
	var ctx = A.ctx;

	function processor() {
		class RangeInput extends AudioWorkletProcessor {
			constructor() {
				super();
				this.buf = new Float32Array(1024); this.n = 0; this.stopped = false;
				this.port.onmessage = (e) => { if (e.data && e.data.stop) this.stopped = true; };
			}
			process(inputs) {
				if (this.stopped) return false;
				var inp = inputs[0];
				if (!inp || !inp.length) return true;
				var ch = inp.length, len = inp[0].length;
				for (var i = 0; i < len; i++) {
					var v = 0;
					for (var c = 0; c < ch; c++) v += inp[c][i];
					this.buf[this.n++] = v / ch;
					if (this.n === this.buf.length) {
						this.port.postMessage(this.buf, [this.buf.buffer]);
						this.buf = new Float32Array(1024); this.n = 0;
					}
				}
				return true;
			}
		}
		registerProcessor('range-input', RangeInput);
	}

	var events = ['pointerdown', 'touchend', 'keydown', 'click'];
	var M = {
		id: (Module.rangeMicNextId = (Module.rangeMicNextId || 0) + 1),
		backend: backend, state: 1, error: '', closed: false, stream: null, nodes: [],
		blocks: 0, ptr: 0, ptrLen: 0, events: events
	};
	M.fail = function (state, msg) { M.state = state; M.error = String(msg || ''); err('[microfone] ' + M.error); };
	M.unlock = function () { if (!M.closed && ctx.state === 'suspended') ctx.resume(); };
	events.forEach(function (t) { document.addEventListener(t, M.unlock, true); });

	/* O modulo do worklet e registrado uma vez por contexto. */
	if (!A.micModule) {
		var url = URL.createObjectURL(new Blob(['(' + processor.toString() + ')();'], { type: 'text/javascript' }));
		A.micModule = ctx.audioWorklet.addModule(url).then(function () { URL.revokeObjectURL(url); });
	}
	var ready = A.micModule;

	navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
	.then(function (stream) {
		if (M.closed) { stream.getTracks().forEach(function (t) { t.stop(); }); return; }
		M.stream = stream;
		return ready.then(function () {
			if (M.closed) return;
			var src = ctx.createMediaStreamSource(stream);
			var node = new AudioWorkletNode(ctx, 'range-input', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] });
			var mute = ctx.createGain(); mute.gain.value = 0;
			src.connect(node); node.connect(mute); mute.connect(ctx.destination);
			M.nodes = [src, node, mute];
			node.port.onmessage = function (e) {
				if (M.closed || !M.backend) return;
				if (typeof document !== 'undefined' && document.hidden) return;
				var data = e.data, n = data.length;
				if (M.ptrLen < n) { if (M.ptr) _free(M.ptr); M.ptr = _malloc(n * 4); M.ptrLen = n; }
				HEAPF32.set(data, M.ptr >> 2);
				M.blocks++;
				_aud_webmic_push(M.backend, M.ptr, n);
			};
			M.state = 2;
			ctx.resume();
		});
	})
	.catch(function (e) {
		if (M.closed) return;
		var name = e && e.name;
		if (name === 'NotAllowedError' || name === 'SecurityError') M.fail(3, 'Microphone blocked: allow it in the browser/app settings');
		else if (name === 'NotFoundError') M.fail(4, 'No microphone found');
		else M.fail(4, 'Microphone failed: ' + e);
	});

	Module.rangeMic = M;
	return M.id;
});

EM_JS(int, aud_webmic_state, (int id), {
	var M = Module.rangeMic;
	if (!M || M.id !== id) return 4;
	/* Liberado mas com o contexto suspenso (falta o primeiro toque): segue pendente. */
	if (M.state === 2 && Module.rangeAudio && Module.rangeAudio.ctx.state !== 'running') return 1;
	return M.state;
});

EM_JS(void, aud_webmic_close, (int id), {
	var M = Module.rangeMic;
	if (!M || M.id !== id) return;
	M.closed = true; M.backend = 0;
	M.events.forEach(function (t) { document.removeEventListener(t, M.unlock, true); });
	M.nodes.forEach(function (n) {
		try { if (n.port) { n.port.onmessage = null; n.port.postMessage({ stop: 1 }); } n.disconnect(); } catch (e) {}
	});
	if (M.stream) M.stream.getTracks().forEach(function (t) { t.stop(); });
	if (M.ptr) _free(M.ptr);
	Module.rangeMic = null;
});

namespace {

using namespace aud;

/* Fila propria: o push vem da thread principal (mensagem do worklet), o poll tambem; sem trava. */
class WebMicrophoneBackend : public IMicrophoneBackend
{
private:
	Specs m_specs;
	int m_id;
	std::vector<sample_t> m_ring;
	size_t m_read;
	size_t m_count;

public:
	WebMicrophoneBackend(Specs specs, int capacity) :
		m_id(0), m_read(0), m_count(0)
	{
		const int rate = aud_webmic_rate();
		if(rate <= 0)
			AUD_THROW(DeviceException, "Web audio output is not running");
		/* A Web entrega mono na taxa do AudioContext; a capacidade segue em segundos. */
		m_specs.rate = SampleRate(rate);
		m_specs.channels = CHANNELS_MONO;
		const double seconds = double(std::max(capacity, 1)) / std::max(double(specs.rate), 1.0);
		m_ring.assign(size_t(std::max(int(seconds * rate), 4096)), 0);
		m_id = aud_webmic_open(this);
		if(!m_id)
			AUD_THROW(DeviceException, "AudioWorklet is not available");
	}

	~WebMicrophoneBackend()
	{
		aud_webmic_close(m_id);
	}

	void push(const float* data, int frames)
	{
		const size_t size = m_ring.size();
		for(int i = 0; i < frames; i++)
		{
			m_ring[(m_read + m_count) % size] = data[i];
			if(m_count < size)
				m_count++;
			else
				m_read = (m_read + 1) % size; // cheia: perde o mais antigo
		}
	}

	Specs getSpecs() const override { return m_specs; }

	MicrophoneState getState() const override { return MicrophoneState(aud_webmic_state(m_id)); }

	int capacity() const override { return int(m_ring.size()); }

	int available() override { return int(m_count); }

	void read(int frames, sample_t* buffer) override
	{
		frames = std::min(frames, int(m_count));
		for(int i = 0; i < frames; i++)
			buffer[i] = m_ring[(m_read + i) % m_ring.size()];
		m_read = (m_read + frames) % m_ring.size();
		m_count -= frames;
	}
};

} // namespace

extern "C" EMSCRIPTEN_KEEPALIVE void aud_webmic_push(void* backend, float* data, int frames)
{
	static_cast<WebMicrophoneBackend*>(backend)->push(data, frames);
}

AUD_NAMESPACE_BEGIN

int WebMicrophone::getPriority()
{
	return 20;
}

std::vector<std::string> WebMicrophone::getDeviceNames()
{
	/* O navegador escolhe o dispositivo (e mostra o seletor no pedido de permissao). */
	return {"Default"};
}

std::shared_ptr<IMicrophoneBackend> WebMicrophone::open(const std::string&, Specs specs, int capacity_frames)
{
	return std::make_shared<WebMicrophoneBackend>(specs, capacity_frames);
}

void WebMicrophone::registerPlugin()
{
	/* Sem https/getUserMedia o microfone fica com estado de erro (sem backend), sem travar o jogo. */
	if(aud_webmic_supported())
		Microphone::registerBackend("WebAudio", std::make_shared<WebMicrophone>());
}

AUD_NAMESPACE_END
