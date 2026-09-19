#pragma once

/**
 * @file WAVFile.h
 * @ingroup plugin
 * Leitor WAV embutido (PCM 8/16/24/32 bits e float 32/64 bits).
 *
 * Existe para o runtime Web/Emscripten, onde libsndfile nao esta disponivel. So le; nao grava.
 */

#include "file/IFileInput.h"

AUD_NAMESPACE_BEGIN

class AUD_API WAVFile : public IFileInput
{
private:
	WAVFile(const WAVFile&) = delete;
	WAVFile& operator=(const WAVFile&) = delete;

public:
	WAVFile();

	/**
	 * Registers this plugin.
	 */
	static void registerPlugin();

	virtual std::shared_ptr<IReader> createReader(std::string filename);
	virtual std::shared_ptr<IReader> createReader(std::shared_ptr<Buffer> buffer);
};

AUD_NAMESPACE_END
