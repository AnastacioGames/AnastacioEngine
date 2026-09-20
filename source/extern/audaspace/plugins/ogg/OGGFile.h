#pragma once

/**
 * @file OGGFile.h
 * @ingroup plugin
 * Leitor Ogg Vorbis embutido, baseado em stb_vorbis (dominio publico / MIT, plugins/ogg/stb_vorbis.c).
 *
 * Existe para o runtime Web/Emscripten, onde FFmpeg e libsndfile nao estao disponiveis. So le.
 * Como o MP3File, nao e um IFileInput registrado (Emscripten sem excecoes): o WAVFile chama
 * createOGGReader() quando o dado comeca com "OggS".
 */

#include "IReader.h"

#include <cstdint>
#include <memory>
#include <vector>

AUD_NAMESPACE_BEGIN

/** Devolve um leitor Ogg Vorbis, ou nullptr se os dados nao forem validos (nunca lanca). */
AUD_API std::shared_ptr<IReader> createOGGReader(std::vector<uint8_t> data);

AUD_NAMESPACE_END
