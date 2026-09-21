/*******************************************************************************
 * Copyright 2009-2016 Jörg Müller
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

#include "file/FileManager.h"
#include "file/IFileInput.h"
#include "file/IFileOutput.h"
#include "Exception.h"
#include "IReader.h"

#ifdef __EMSCRIPTEN__
#include <cstdio>
#endif

AUD_NAMESPACE_BEGIN

#ifdef __EMSCRIPTEN__
namespace {

/** Leitor de um som que nao pode ser decodificado. O Wasm nao tem excecoes, e um leitor nulo
 *  derrubaria os leitores de efeito (volume, limit, pitch...) que desreferenciam o filho; este
 *  toca silencio de comprimento zero e deixa .specs/.length/.play seguros. */
class UnreadableReader : public IReader
{
public:
	virtual bool isSeekable() const { return true; }
	virtual void seek(int) {}
	virtual int getLength() const { return 0; }
	virtual int getPosition() const { return 0; }
	virtual Specs getSpecs() const { Specs s; s.rate = RATE_44100; s.channels = CHANNELS_MONO; return s; }
	virtual void read(int &length, bool &eos, sample_t *)
	{
		length = 0;
		eos = true;
	}
};

std::shared_ptr<IReader> unreadableReader()
{
	fprintf(stderr, "[aud] file could not be decoded; using a silent empty sound\n");
	return std::make_shared<UnreadableReader>();
}

}  // namespace
#endif

std::list<std::shared_ptr<IFileInput>>& FileManager::inputs()
{
	static std::list<std::shared_ptr<IFileInput>> inputs;
	return inputs;
}

std::list<std::shared_ptr<IFileOutput>>& FileManager::outputs()
{
	static std::list<std::shared_ptr<IFileOutput>> outputs;
	return outputs;
}

void FileManager::registerInput(std::shared_ptr<IFileInput> input)
{
	inputs().push_back(input);
}

void FileManager::registerOutput(std::shared_ptr<aud::IFileOutput> output)
{
	outputs().push_back(output);
}

std::shared_ptr<IReader> FileManager::createReader(std::string filename)
{
	for(std::shared_ptr<IFileInput> input : inputs())
	{
		try
		{
			std::shared_ptr<IReader> reader = input->createReader(filename);
#ifdef __EMSCRIPTEN__
			if(!reader)
				continue;
#endif
			return reader;
		}
		catch(Exception&) {}
	}

#ifdef __EMSCRIPTEN__
	/* Emscripten is built without C++ exceptions.  A decode failure is an
	 * expected result for user supplied media, not a reason to abort Wasm. */
	return unreadableReader();
#else
	AUD_THROW(FileException, "The file couldn't be read with any installed file reader.");
#endif
}

std::shared_ptr<IReader> FileManager::createReader(std::shared_ptr<Buffer> buffer)
{
	for(std::shared_ptr<IFileInput> input : inputs())
	{
		try
		{
			std::shared_ptr<IReader> reader = input->createReader(buffer);
#ifdef __EMSCRIPTEN__
			if(!reader)
				continue;
#endif
			return reader;
		}
		catch(Exception&) {}
	}

#ifdef __EMSCRIPTEN__
	return unreadableReader();
#else
	AUD_THROW(FileException, "The file couldn't be read with any installed file reader.");
#endif
}

std::shared_ptr<IWriter> FileManager::createWriter(std::string filename, DeviceSpecs specs, Container format, Codec codec, unsigned int bitrate)
{
	for(std::shared_ptr<IFileOutput> output : outputs())
	{
		try
		{
			return output->createWriter(filename, specs, format, codec, bitrate);
		}
		catch(Exception&) {}
	}

	AUD_THROW(FileException, "The file couldn't be written with any installed writer.");
}

AUD_NAMESPACE_END
