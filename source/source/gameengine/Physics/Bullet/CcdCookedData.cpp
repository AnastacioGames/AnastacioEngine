/** \file gameengine/Physics/Bullet/CcdCookedData.cpp
 *  \ingroup physbullet
 */

#include "CcdCookedData.h"

#include "CM_Message.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <mutex>
#include <utility>

extern "C" {
#  include "BLI_fileops.h"
#  include "BLI_string.h"
#  include "BLI_path_util.h"
}

namespace CcdCookedData
{
static const char magic[8] = {'A', 'N', 'A', 'C', 'O', 'O', 'K', '2'};
static const uint32_t kindHull = 1;
static const uint32_t kindShader = 2;
static const uint32_t kindMesh = 3;
static const uint32_t kindBvh = 4;
static const char userMagic[8] = {'A', 'N', 'A', 'S', 'H', 'A', 'D', '1'};

// Key: hash of the vertex bytes and the vertex count.
typedef std::pair<uint64_t, uint32_t> Key;

static std::mutex mutex;
static std::map<Key, std::vector<btScalar> > hulls;
struct Shader
{
	uint32_t format;
	std::vector<char> data;
	// From or for the user shader cache.
	bool user;
};
static std::map<uint64_t, Shader> shaders;
static std::map<uint64_t, std::vector<char> > meshes;
static std::map<uint64_t, std::vector<char> > bvhs;
static std::string filePath;
static bool record = false;
// Cook button: the file is rewritten even with nothing in it (removed then).
static bool cooking = false;
// Exported game: its own shaders go to this file (empty otherwise).
static std::string userPath;
static uint64_t device = 0;
static bool warmUp = false;
static unsigned int numLoaded = 0, numHits = 0, numAdded = 0;
static unsigned int numShadersLoaded = 0, numShaderHits = 0, numShadersAdded = 0;
static unsigned int numMeshesLoaded = 0, numMeshHits = 0, numMeshesAdded = 0;
static unsigned int numBvhsLoaded = 0, numBvhHits = 0, numBvhsAdded = 0;

static_assert(sizeof(btScalar) == sizeof(uint32_t), "the vertex hash reads floats");

static uint64_t Mix(uint64_t x)
{
	// splitmix64 finalizer.
	x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
	x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
	return x ^ (x >> 31);
}

/* The display arrays don't keep the vertices in the same order for the same mesh,
 * so the hash only depends on the set of vertices: per vertex hashes are summed. */
static Key MakeKey(const btScalar *vertices, unsigned int numVertices)
{
	uint64_t sum = 0, sumMixed = 0;
	for (unsigned int i = 0; i < numVertices; ++i) {
		uint64_t hash = 0;
		for (unsigned int j = 0; j < 3; ++j) {
			uint32_t bits;
			memcpy(&bits, &vertices[i * 3 + j], sizeof(bits));
			hash = Mix(hash ^ bits);
		}
		sum += hash;
		sumMixed += Mix(hash);
	}
	return Key(sum ^ Mix(sumMixed), numVertices);
}

/** Every record: kind, hash, two counts, then its data (hull: count2 points; shader: format, count2 bytes;
 *  mesh: count2 bytes). */
static void ReadRecords(FILE *file, bool user)
{
	uint32_t kind, count1, count2;
	uint64_t hash;
	while (fread(&kind, 4, 1, file) == 1 && fread(&hash, 8, 1, file) == 1 && fread(&count1, 4, 1, file) == 1 &&
	       fread(&count2, 4, 1, file) == 1)
	{
		if (kind == kindHull && !user) {
			std::vector<btScalar> points((size_t)count2 * 3);
			if (fread(points.data(), sizeof(btScalar), points.size(), file) != points.size()) {
				break;
			}
			hulls[Key(hash, count1)] = std::move(points);
			++numLoaded;
		}
		else if (kind == kindShader) {
			Shader& shader = shaders[hash];
			shader.format = count1;
			shader.user = user;
			shader.data.resize(count2);
			if (fread(shader.data.data(), 1, count2, file) != count2) {
				shaders.erase(hash);
				break;
			}
			++numShadersLoaded;
		}
		else if ((kind == kindMesh || kind == kindBvh) && !user) {
			std::map<uint64_t, std::vector<char> >& blobs = (kind == kindMesh) ? meshes : bvhs;
			std::vector<char>& data = blobs[hash];
			data.resize(count2);
			if (fread(data.data(), 1, count2, file) != count2) {
				blobs.erase(hash);
				break;
			}
			++((kind == kindMesh) ? numMeshesLoaded : numBvhsLoaded);
		}
		else {
			break;
		}
	}
}

static std::string UserCacheDir()
{
#ifdef _WIN32
	const char *base = getenv("LOCALAPPDATA");
	return (base && base[0]) ? std::string(base) + "\\AnastacioEngine\\ShaderCache" : std::string();
#else
	const char *base = getenv("XDG_CACHE_HOME");
	if (base && base[0]) {
		return std::string(base) + "/AnastacioEngine/ShaderCache";
	}
	base = getenv("HOME");
	return (base && base[0]) ? std::string(base) + "/.cache/AnastacioEngine/ShaderCache" : std::string();
#endif
}

/// Shader cache of the exported game: its name plus a hash of its path (two games may share a name).
static void OpenUserCache(const char *gamePath)
{
	const std::string dir = UserCacheDir();
	if (dir.empty()) {
		return;
	}
	uint64_t pathHash = 14695981039346656037ULL;
	for (const char *c = gamePath; *c; ++c) {
		unsigned char ch = (unsigned char)*c;
#ifdef _WIN32
		// The editor gives "D:/game\x.blend", the player "D:\game\x.blend": one cache for both.
		if (ch == '/') {
			ch = '\\';
		}
#endif
		pathHash = (pathHash ^ ch) * 1099511628211ULL;
	}
	char name[FILE_MAX], hex[32];
	BLI_strncpy(name, BLI_path_basename(gamePath), sizeof(name));
	BLI_path_extension_replace(name, sizeof(name), "");
	BLI_snprintf(hex, sizeof(hex), "-%016llx.shaders", (unsigned long long)pathHash);
	userPath = dir + SEP_STR + name + hex;
	record = false;
	warmUp = true;

	FILE *file = BLI_fopen(userPath.c_str(), "rb");
	if (!file) {
		return;
	}
	char head[8];
	uint64_t fileDevice;
	if (fread(head, 1, 8, file) == 8 && memcmp(head, userMagic, 8) == 0 && fread(&fileDevice, 8, 1, file) == 1 &&
	    fileDevice == device)
	{
		ReadRecords(file, true);
		warmUp = false;
	}
	fclose(file);
}

void Open(const std::string& mainFile, unsigned long long deviceKey)
{
	std::lock_guard<std::mutex> lock(mutex);
	hulls.clear();
	shaders.clear();
	meshes.clear();
	bvhs.clear();
	numLoaded = numHits = numAdded = 0;
	numShadersLoaded = numShaderHits = numShadersAdded = 0;
	numMeshesLoaded = numMeshHits = numMeshesAdded = 0;
	numBvhsLoaded = numBvhHits = numBvhsAdded = 0;
	filePath.clear();
	userPath.clear();
	record = cooking = warmUp = false;
	device = deviceKey;
	if (mainFile.empty()) {
		return;
	}

	// Cook button: the game runs from a temporary copy and writes a clean file next to the real .blend.
	const char *cookPath = getenv("ANASTACIO_COOK");
	if (cookPath && cookPath[0]) {
		filePath = cookPath;
		record = cooking = true;
		return;
	}

	char path[FILE_MAX];
	BLI_strncpy(path, mainFile.c_str(), sizeof(path));
	record = BLI_path_extension_check(path, ".blend");
	BLI_path_extension_replace(path, sizeof(path), ".cooked");
	filePath = path;

	FILE *file = BLI_fopen(path, "rb");
	if (file) {
		char head[8];
		uint32_t version;
		if (fread(head, 1, 8, file) == 8 && memcmp(head, magic, 8) == 0 && fread(&version, 4, 1, file) == 1 &&
		    version == sizeof(btScalar))
		{
			ReadRecords(file, false);
		}
		else {
			CM_Warning("[Cooked] ignoring " << path << ": unknown format");
		}
		fclose(file);
	}

	// Exported game: the cooked file is read-only, its own shaders go to the user cache (read after it).
	if (!record && device) {
		OpenUserCache(mainFile.c_str());
	}
}

/// Writes a complete file next to the old one, then replaces it. user: only the user shader cache records.
static bool WriteFile(const std::string& path, bool user)
{
	const std::string tmpPath = path + ".tmp";
	FILE *file = BLI_fopen(tmpPath.c_str(), "wb");
	bool ok = file != nullptr;
	if (ok) {
		if (user) {
			ok = fwrite(userMagic, 1, 8, file) == 8 && fwrite(&device, 8, 1, file) == 1;
		}
		else {
			const uint32_t version = sizeof(btScalar);
			ok = fwrite(magic, 1, 8, file) == 8 && fwrite(&version, 4, 1, file) == 1;
			for (const auto& item : hulls) {
				const uint32_t numPoints = (uint32_t)(item.second.size() / 3);
				ok = ok && fwrite(&kindHull, 4, 1, file) == 1 && fwrite(&item.first.first, 8, 1, file) == 1 &&
				     fwrite(&item.first.second, 4, 1, file) == 1 && fwrite(&numPoints, 4, 1, file) == 1 &&
				     fwrite(item.second.data(), sizeof(btScalar), item.second.size(), file) == item.second.size();
			}
			const uint32_t zero = 0;
			for (const auto& item : bvhs) {
				const uint32_t size = (uint32_t)item.second.size();
				ok = ok && fwrite(&kindBvh, 4, 1, file) == 1 && fwrite(&item.first, 8, 1, file) == 1 &&
				     fwrite(&zero, 4, 1, file) == 1 && fwrite(&size, 4, 1, file) == 1 &&
				     fwrite(item.second.data(), 1, size, file) == size;
			}
			for (const auto& item : meshes) {
				const uint32_t size = (uint32_t)item.second.size();
				ok = ok && fwrite(&kindMesh, 4, 1, file) == 1 && fwrite(&item.first, 8, 1, file) == 1 &&
				     fwrite(&zero, 4, 1, file) == 1 && fwrite(&size, 4, 1, file) == 1 &&
				     fwrite(item.second.data(), 1, size, file) == size;
			}
		}
		for (const auto& item : shaders) {
			if (user && !item.second.user) {
				continue;
			}
			const uint32_t size = (uint32_t)item.second.data.size();
			ok = ok && fwrite(&kindShader, 4, 1, file) == 1 && fwrite(&item.first, 8, 1, file) == 1 &&
			     fwrite(&item.second.format, 4, 1, file) == 1 && fwrite(&size, 4, 1, file) == 1 &&
			     fwrite(item.second.data.data(), 1, size, file) == size;
		}
		ok = (fclose(file) == 0) && ok;
	}
	if (ok) {
		if (BLI_exists(path.c_str())) {
			BLI_delete(path.c_str(), false, false);
		}
		ok = BLI_rename(tmpPath.c_str(), path.c_str()) == 0;
	}
	if (!ok) {
		BLI_delete(tmpPath.c_str(), false, false);
		CM_Warning("[Cooked] could not write " << path);
	}
	return ok;
}

void Close()
{
	std::lock_guard<std::mutex> lock(mutex);
	const bool added = numAdded || numShadersAdded || numMeshesAdded || numBvhsAdded;
	if (!filePath.empty() && (numLoaded || numShadersLoaded || numMeshesLoaded || numBvhsLoaded || added)) {
		CM_Message("[Cooked] " << filePath << ": hulls " << numLoaded << " loaded, " << numHits << " used, "
		           << numAdded << " new; shaders " << numShadersLoaded << " loaded, " << numShaderHits << " used, "
		           << numShadersAdded << " new; meshes " << numMeshesLoaded << " loaded, " << numMeshHits << " used, "
		           << numMeshesAdded << " new; bvh " << numBvhsLoaded << " loaded, " << numBvhHits << " used, "
		           << numBvhsAdded << " new" << (userPath.empty() ? "" : " (user cache " + userPath + ")"));
	}
	if (cooking && !added) {
		if (BLI_exists(filePath.c_str())) {
			BLI_delete(filePath.c_str(), false, false);
		}
	}
	else if (record && added) {
		WriteFile(filePath, false);
	}
	// Written after a warm-up even when empty, so it isn't done again on every start.
	if (!userPath.empty() && (numShadersAdded || warmUp)) {
		char dir[FILE_MAX];
		BLI_split_dir_part(userPath.c_str(), dir, sizeof(dir));
		BLI_dir_create_recursive(dir);
		WriteFile(userPath, true);
	}
	hulls.clear();
	shaders.clear();
	meshes.clear();
	bvhs.clear();
	filePath.clear();
	userPath.clear();
	record = cooking = warmUp = false;
}

bool NeedsWarmUp()
{
	std::lock_guard<std::mutex> lock(mutex);
	return warmUp;
}

bool FindHull(const btScalar *vertices, unsigned int numVertices, std::vector<btScalar>& points)
{
	const Key key = MakeKey(vertices, numVertices);
	std::lock_guard<std::mutex> lock(mutex);
	const auto it = hulls.find(key);
	if (it == hulls.end()) {
		return false;
	}
	points = it->second;
	++numHits;
	return true;
}

void AddHull(const btScalar *vertices, unsigned int numVertices, const btScalar *points, unsigned int numPoints)
{
	if (!record) {
		return;
	}
	const Key key = MakeKey(vertices, numVertices);
	std::lock_guard<std::mutex> lock(mutex);
	if (record && hulls.emplace(key, std::vector<btScalar>(points, points + (size_t)numPoints * 3)).second) {
		++numAdded;
	}
}

const void *FindShader(unsigned long long key, unsigned int *format, int *size)
{
	std::lock_guard<std::mutex> lock(mutex);
	const auto it = shaders.find(key);
	if (it == shaders.end()) {
		return nullptr;
	}
	++numShaderHits;
	*format = it->second.format;
	*size = (int)it->second.data.size();
	return it->second.data.data();
}

void AddShader(unsigned long long key, unsigned int format, const void *data, int size)
{
	std::lock_guard<std::mutex> lock(mutex);
	if (!(record || !userPath.empty()) || size <= 0) {
		return;
	}
	Shader& shader = shaders[key];
	shader.user = !userPath.empty();
	// A binary the driver rejected is replaced by the new one.
	shader.format = format;
	shader.data.assign((const char *)data, (const char *)data + size);
	++numShadersAdded;
}

const std::vector<char> *FindMesh(unsigned long long key)
{
	std::lock_guard<std::mutex> lock(mutex);
	const auto it = meshes.find(key);
	if (it == meshes.end()) {
		return nullptr;
	}
	++numMeshHits;
	return &it->second;
}

bool IsRecording()
{
	std::lock_guard<std::mutex> lock(mutex);
	return record;
}

void AddMesh(unsigned long long key, const std::vector<char>& data)
{
	std::lock_guard<std::mutex> lock(mutex);
	if (record && !data.empty() && meshes.emplace(key, data).second) {
		++numMeshesAdded;
	}
}

const std::vector<char> *FindBvh(unsigned long long key)
{
	std::lock_guard<std::mutex> lock(mutex);
	const auto it = bvhs.find(key);
	if (it == bvhs.end()) {
		return nullptr;
	}
	++numBvhHits;
	return &it->second;
}

void AddBvh(unsigned long long key, const std::vector<char>& data)
{
	std::lock_guard<std::mutex> lock(mutex);
	if (record && !data.empty() && bvhs.emplace(key, data).second) {
		++numBvhsAdded;
	}
}
}
