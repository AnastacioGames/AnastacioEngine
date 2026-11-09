// Testa o PitchDetector com sinais de frequencia conhecida, sem microfone.
#include "util/PitchDetector.h"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

static const float RATE = 22050.0f;
static const int COUNT = 1024;
static const double TAU = 6.283185307179586;

enum Sinal { SENO, VOZ, SEM_FUNDAMENTAL };

static std::vector<float> gerar(double f, Sinal tipo, float ruido, double fase)
{
	std::vector<float> s(COUNT);
	for(int i = 0; i < COUNT; i++)
	{
		const double x = TAU * f * i / RATE + fase;
		double v = std::sin(x);
		if(tipo != SENO)
		{
			v = tipo == VOZ ? 1.0 * std::sin(x) : 0.15 * std::sin(x);
			/* Harmonicos so ate perto de Nyquist, como um som captado de verdade. */
			for(int h = 2; h <= 8 && f * h < RATE * 0.45; h++)
				v += (tipo == VOZ ? 0.8 : 1.0) / h * std::sin(h * x + 0.7 * h);
			v *= 0.4;
		}
		else
			v *= 0.5;
		s[i] = float(v + ruido * (std::rand() / float(RAND_MAX) * 2.0f - 1.0f));
	}
	return s;
}

static int falhas = 0;

static void varrer(const char* nome, Sinal tipo, float ruido)
{
	aud::PitchDetector d;
	double pior = 0.0;
	int total = 0, erros = 0;
	for(int midi = 40; midi <= 84; midi++) /* E2 a C6 */
	{
		for(double desvio : {-37.0, 0.0, 23.0})
		{
			for(double fase : {0.0, 1.1, 2.7})
			{
				const double f = 440.0 * std::pow(2.0, (midi + desvio / 100.0 - 69.0) / 12.0);
				std::vector<float> s = gerar(f, tipo, ruido, fase);
				const aud::PitchResult r = d.detect(s.data(), COUNT, RATE);
				total++;
				const double erro = r.frequency > 0.0f ? std::fabs(1200.0 * std::log2(r.frequency / f)) : 1e9;
				if(erro > 10.0)
					erros++;
				else if(erro > pior)
					pior = erro;
			}
		}
	}
	std::printf("%-22s pior acerto %.2f cents; fora de 10 cents ou sem nota: %d/%d\n", nome, pior, erros, total);
	if(erros * 100 > total)
		falhas++;
}

int main()
{
	varrer("seno limpo", SENO, 0.0f);
	varrer("voz (harmonicos)", VOZ, 0.0f);
	varrer("voz + ruido 2%", VOZ, 0.02f);
	varrer("voz + ruido 10%", VOZ, 0.10f);
	varrer("fundamental fraca", SEM_FUNDAMENTAL, 0.01f);

	aud::PitchDetector d;
	std::vector<float> s(COUNT, 0.0f);
	aud::PitchResult r = d.detect(s.data(), COUNT, RATE);
	std::printf("silencio: %.1f Hz\n", r.frequency);
	if(r.frequency != 0.0f)
		falhas++;

	int falsos = 0;
	for(int n = 0; n < 200; n++)
	{
		for(float& v : s)
			v = 0.3f * (std::rand() / float(RAND_MAX) * 2.0f - 1.0f);
		if(d.detect(s.data(), COUNT, RATE).frequency != 0.0f)
			falsos++;
	}
	std::printf("ruido puro com nota falsa: %d/200\n", falsos);
	if(falsos > 4)
		falhas++;

	aud::NoteResult a = aud::PitchDetector::note(440.0f), b = aud::PitchDetector::note(452.0f), c = aud::PitchDetector::note(432.0f, 432.0f);
	std::printf("440 Hz: midi %d %+.1f | 452 Hz: midi %d %+.1f | 432 com A4=432: midi %d %+.1f\n",
	            a.midi, a.cents, b.midi, b.cents, c.midi, c.cents);
	if(a.midi != 69 || std::fabs(a.cents) > 0.01f || b.midi != 69 || std::fabs(b.cents - 46.6f) > 0.5f || c.midi != 69)
		falhas++;

	s = gerar(82.41, VOZ, 0.01f, 0.0);
	auto ini = std::chrono::steady_clock::now();
	for(int n = 0; n < 1000; n++)
		r = d.detect(s.data(), COUNT, RATE);
	double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - ini).count() / 1000.0;
	std::printf("custo: %.3f ms por detecao (janela de %.0f ms)\n", ms, COUNT * 1000.0 / RATE);

	std::printf(falhas ? "FALHOU (%d)\n" : "OK\n", falhas);
	return falhas ? 1 : 0;
}
