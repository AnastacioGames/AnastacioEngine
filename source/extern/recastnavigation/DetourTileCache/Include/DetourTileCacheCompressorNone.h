// Range Engine addition, not part of upstream recastnavigation.
// Passthrough dtTileCacheCompressor: tile layers are kept uncompressed in memory,
// so no extra compression library (e.g. fastlz) is needed.

#ifndef DETOURTILECACHECOMPRESSORNONE_H
#define DETOURTILECACHECOMPRESSORNONE_H

#include <string.h>

#include "DetourTileCacheBuilder.h"

struct dtTileCacheCompressorNone : public dtTileCacheCompressor
{
	virtual int maxCompressedSize(const int bufferSize)
	{
		return bufferSize;
	}

	virtual dtStatus compress(const unsigned char* buffer, const int bufferSize,
							  unsigned char* compressed, const int maxCompressedSize, int* compressedSize)
	{
		if (bufferSize > maxCompressedSize)
			return DT_FAILURE | DT_BUFFER_TOO_SMALL;
		memcpy(compressed, buffer, bufferSize);
		*compressedSize = bufferSize;
		return DT_SUCCESS;
	}

	virtual dtStatus decompress(const unsigned char* compressed, const int compressedSize,
								unsigned char* buffer, const int maxBufferSize, int* bufferSize)
	{
		if (compressedSize > maxBufferSize)
			return DT_FAILURE | DT_BUFFER_TOO_SMALL;
		memcpy(buffer, compressed, compressedSize);
		*bufferSize = compressedSize;
		return DT_SUCCESS;
	}
};

#endif // DETOURTILECACHECOMPRESSORNONE_H
