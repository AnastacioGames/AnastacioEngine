#pragma once

/**
 * @file MP3File.h
 * @ingroup plugin
 * Leitor MP3 embutido, baseado em dr_mp3 (dominio publico / MIT-0, plugins/mp3/dr_mp3.h).
 *
 * Existe para o runtime Web/Emscripten, onde FFmpeg e libsndfile nao estao disponiveis. So le; nao grava.
 * Decodifica sob demanda (streaming), sem expandir o arquivo inteiro para PCM.
 *
 * Nao e um IFileInput registrado: o Emscripten roda sem excecoes C++, e o FileManager depende de
 * try/catch para pular leitores que nao reconhecem o arquivo. Por isso o WAVFile (unico plugin
 * registrado no Web) chama createMP3Reader() quando o dado nao e RIFF/WAVE.
 */

#include "IReader.h"

#include <cstdint>
#include <memory>
#include <vector>

AUD_NAMESPACE_BEGIN

/** Devolve um leitor MP3, ou nullptr se os dados nao forem um MP3 valido (nunca lanca). */
AUD_API std::shared_ptr<IReader> createMP3Reader(std::vector<uint8_t> data);

AUD_NAMESPACE_END
