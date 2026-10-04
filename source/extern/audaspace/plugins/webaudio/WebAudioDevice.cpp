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

#include "WebAudioDevice.h"
#include "devices/DeviceManager.h"
#include "devices/IDeviceFactory.h"

#include <emscripten.h>

/* Fluxo: o AudioWorkletProcessor pede pela porta os frames que faltam para a fila chegar ao alvo
 * (multiplos de `block`); a thread principal mixa (WebAudioDevice::mixBlock) e devolve um Float32Array
 * intercalado transferido. O alvo comeca em dois blocos. Faltando dados (a thread principal
 * ficou presa num quadro longo), o worklet toca silencio, conta underruns e, quando os dados voltam,
 * soma ao alvo o que faltou, ate ~0,5 s. Assim o primeiro pico ja dimensiona a fila.
 * Estado exposto em Module.rangeAudio (contexto, contadores) para a pagina e os testes. */

EM_JS(int, aud_webaudio_supported, (), {
	if (typeof AudioWorkletNode === 'undefined') return 0;
	if (typeof AudioContext === 'undefined' && typeof webkitAudioContext === 'undefined') return 0;
	if (typeof isSecureContext !== 'undefined' && !isSecureContext) return 0;
	try { if (/[?&]audio=sdl(&|$)/.test(location.search)) return 0; } catch (e) {}
	return 1;
});

EM_JS(int, aud_webaudio_open, (int channels, int block, void* device), {
	var AC = typeof AudioContext !== 'undefined' ? AudioContext : webkitAudioContext;
	var ctx;
	try { ctx = new AC({ latencyHint: 'interactive' }); } catch (e) { return 0; }
	if (!ctx.audioWorklet) { ctx.close(); return 0; }

	function processor() {
		class RangeOutput extends AudioWorkletProcessor {
			constructor(options) {
				super();
				var o = options.processorOptions;
				this.ch = o.channels; this.block = o.block;
				this.target = 2 * o.block;
				this.maxTarget = Math.max(this.target, Math.ceil(0.5 * sampleRate / o.block) * o.block);
				this.queue = []; this.offset = 0; this.queued = 0; this.pending = 0;
				this.underruns = 0; this.missing = 0; this.started = false; this.stopped = false;
				this.port.onmessage = (e) => {
					var d = e.data;
					if (d.stop) { this.stopped = true; return; }
					this.queue.push(d.buf); this.queued += d.frames; this.pending -= d.frames; this.started = true;
				};
				this.request();
			}
			request() {
				var missing = this.target - this.queued - this.pending;
				if (missing <= 0) return;
				var need = Math.ceil(missing / this.block) * this.block;
				this.pending += need;
				this.port.postMessage({ need: need, underruns: this.underruns, target: this.target });
			}
			process(inputs, outputs) {
				if (this.stopped) return false;
				var out = outputs[0], n = out[0].length, ch = this.ch, i = 0;
				while (i < n && this.queue.length) {
					var buf = this.queue[0], frames = buf.length / ch;
					var take = Math.min(frames - this.offset, n - i);
					for (var c = 0; c < out.length; c++) {
						var dst = out[c], src = (c < ch ? c : 0) + this.offset * ch;
						for (var k = 0; k < take; k++) dst[i + k] = buf[src + k * ch];
					}
					i += take; this.offset += take; this.queued -= take;
					if (this.offset >= frames) { this.queue.shift(); this.offset = 0; }
				}
				if (i < n && this.started) {
					this.underruns++;
					this.missing += n - i;
				}
				else if (i === n && this.missing) {
					var grow = Math.ceil(this.missing / this.block) * this.block;
					this.target = Math.min(this.maxTarget, this.target + grow);
					this.missing = 0;
				}
				this.request();
				return true;
			}
		}
		registerProcessor('range-output', RangeOutput);
	}

	var A = {
		id: (Module.rangeAudioNextId = (Module.rangeAudioNextId || 0) + 1),
		backend: 'AudioWorklet', ctx: ctx, node: null, device: device, playing: false, closed: false,
		blocks: 0, frames: 0, peak: 0, underruns: 0
	};
	A.unlock = function () { if (!A.closed && ctx.state === 'suspended') ctx.resume(); };
	A.events = ['pointerdown', 'mousedown', 'touchend', 'keydown', 'click'];
	A.events.forEach(function (t) { document.addEventListener(t, A.unlock, true); });
	ctx.addEventListener('statechange', function () {
		if (ctx.state === 'running') A.events.forEach(function (t) { document.removeEventListener(t, A.unlock, true); });
	});
	ctx.resume();

	var url = URL.createObjectURL(new Blob(['(' + processor.toString() + ')();'], { type: 'text/javascript' }));
	ctx.audioWorklet.addModule(url).then(function () {
		URL.revokeObjectURL(url);
		if (A.closed) return;
		var node = new AudioWorkletNode(ctx, 'range-output', {
			numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [channels],
			processorOptions: { channels: channels, block: block }
		});
		node.port.onmessage = function (e) {
			if (A.closed || !A.device) return;
			var frames = e.data.need, len = frames * channels, buf;
			A.underruns = e.data.underruns; A.target = e.data.target;
			if (A.playing) {
				var ptr = _aud_webaudio_mix(A.device, frames) >> 2;
				buf = HEAPF32.slice(ptr, ptr + len);
				for (var i = 0; i < len; i++) { var v = buf[i] < 0 ? -buf[i] : buf[i]; if (v > A.peak) A.peak = v; }
			}
			else buf = new Float32Array(len);
			A.blocks++; A.frames += frames;
			node.port.postMessage({ buf: buf, frames: frames }, [buf.buffer]);
		};
		node.connect(ctx.destination);
		A.node = node;
	}).catch(function (e) {
		err('[audio] AudioWorklet falhou: ' + e);
	});

	Module.rangeAudio = A;
	return A.id;
});

EM_JS(int, aud_webaudio_rate, (int id), {
	var A = Module.rangeAudio;
	return A && A.id === id ? A.ctx.sampleRate : 0;
});

EM_JS(void, aud_webaudio_playing, (int id, int playing), {
	var A = Module.rangeAudio;
	if (A && A.id === id) A.playing = !!playing;
});

EM_JS(void, aud_webaudio_close, (int id), {
	var A = Module.rangeAudio;
	if (!A || A.id !== id) return;
	A.closed = true; A.device = 0;
	A.events.forEach(function (t) { document.removeEventListener(t, A.unlock, true); });
	if (A.node) { A.node.port.onmessage = null; A.node.port.postMessage({ stop: 1 }); A.node.disconnect(); }
	A.ctx.close();
	Module.rangeAudio = null;
});

extern "C" EMSCRIPTEN_KEEPALIVE float* aud_webaudio_mix(void* device, int frames)
{
	return static_cast<aud::WebAudioDevice*>(device)->mixBlock(frames);
}

AUD_NAMESPACE_BEGIN

void WebAudioDevice::playing(bool playing)
{
	m_playback = playing;
	aud_webaudio_playing(m_id, playing ? 1 : 0);
}

WebAudioDevice::WebAudioDevice(DeviceSpecs specs, int buffersize) :
	m_playback(false), m_id(0)
{
	/* O worklet recebe float32; 1 ou 2 canais (o destino faz o upmix de mono). */
	if(specs.channels != CHANNELS_MONO)
		specs.channels = CHANNELS_STEREO;
	specs.format = FORMAT_FLOAT32;
	if(buffersize < 128)
		buffersize = AUD_DEFAULT_BUFFER_SIZE;

	m_id = aud_webaudio_open(specs.channels, buffersize, this);

	/* Mixa na taxa do contexto (a do hardware), como o SDL fazia: o navegador nao reamostra. */
	int rate = m_id ? aud_webaudio_rate(m_id) : 0;
	specs.rate = rate > 0 ? (SampleRate)rate : RATE_48000;

	m_specs = specs;
	m_buffer.resize(buffersize * specs.channels);

	create();
}

WebAudioDevice::~WebAudioDevice()
{
	aud_webaudio_close(m_id);

	destroy();
}

float* WebAudioDevice::mixBlock(int frames)
{
	if(m_buffer.size() < size_t(frames) * m_specs.channels)
		m_buffer.resize(size_t(frames) * m_specs.channels);

	mix(reinterpret_cast<data_t*>(m_buffer.data()), frames);

	return m_buffer.data();
}

class WebAudioDeviceFactory : public IDeviceFactory
{
private:
	DeviceSpecs m_specs;
	int m_buffersize;

public:
	WebAudioDeviceFactory() :
		m_buffersize(AUD_DEFAULT_BUFFER_SIZE)
	{
		m_specs.format = FORMAT_FLOAT32;
		m_specs.channels = CHANNELS_STEREO;
		m_specs.rate = RATE_48000;
	}

	virtual std::shared_ptr<IDevice> openDevice()
	{
		return std::shared_ptr<IDevice>(new WebAudioDevice(m_specs, m_buffersize));
	}

	virtual int getPriority()
	{
		/* Acima do SDL (1 << 5): e o padrao quando o navegador suporta AudioWorklet. */
		return 1 << 6;
	}

	virtual void setSpecs(DeviceSpecs specs)
	{
		m_specs = specs;
	}

	virtual void setBufferSize(int buffersize)
	{
		m_buffersize = buffersize;
	}

	virtual void setName(std::string name)
	{
	}
};

void WebAudioDevice::registerPlugin()
{
	/* Sem suporte (contexto inseguro, navegador antigo, ?audio=sdl) o SDL segue como saida. */
	if(aud_webaudio_supported())
		DeviceManager::registerDevice("WebAudio", std::shared_ptr<IDeviceFactory>(new WebAudioDeviceFactory));
}

AUD_NAMESPACE_END
