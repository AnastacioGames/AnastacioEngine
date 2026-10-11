/*
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 */

/** \file blender/gpu/intern/gpu_shader_editor_cache.c
 *  \ingroup gpu
 *
 * Program binaries of the viewport material shaders, kept between editor sessions in the user cache folder
 * (%LOCALAPPDATA%\AnastacioEngine\ShaderCache\editor.shaders), so showing a layer or opening a file again doesn't
 * compile its materials again. Default hooks of GPU_shader_binary_cache_set: the game (Play) sets its own cooked
 * hooks while it runs. RANGE_NO_EDITOR_SHADER_CACHE=1 turns it off.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "MEM_guardedalloc.h"

#include "BLI_utildefines.h"
#include "BLI_fileops.h"
#include "BLI_ghash.h"
#include "BLI_path_util.h"
#include "BLI_string.h"

#include "GPU_init_exit.h"
#include "GPU_shader.h"

typedef struct CacheEntry {
	unsigned long long key;
	unsigned int format;
	int size;
	/* data follows */
} CacheEntry;

#define ENTRY_DATA(entry) ((const void *)((entry) + 1))

/* Past this the cache stops growing (new materials still compile, they just aren't kept). */
#define CACHE_MAX_BYTES (256u * 1024u * 1024u)

static const char cache_magic[8] = {'R', 'N', 'G', 'E', 'D', 'S', 'H', '1'};

static GHash *cache_entries = NULL;
static char cache_path[FILE_MAX] = "";
static unsigned long long cache_device = 0;
static size_t cache_bytes = 0;
static bool cache_dirty = false;

static unsigned int entry_hash(const void *key)
{
	const unsigned long long k = *(const unsigned long long *)key;
	return (unsigned int)(k ^ (k >> 32));
}

static bool entry_cmp(const void *a, const void *b)
{
	/* GHash compare: false when equal. */
	return *(const unsigned long long *)a != *(const unsigned long long *)b;
}

static void entry_put(CacheEntry *entry)
{
	CacheEntry *old = BLI_ghash_popkey(cache_entries, &entry->key, NULL);
	if (old) {
		cache_bytes -= (size_t)old->size;
		MEM_freeN(old);
	}
	BLI_ghash_insert(cache_entries, &entry->key, entry);
	cache_bytes += (size_t)entry->size;
}

static const void *editor_cache_find(unsigned long long key, unsigned int *format, int *size)
{
	const CacheEntry *entry = BLI_ghash_lookup(cache_entries, &key);
	if (!entry) {
		return NULL;
	}
	*format = entry->format;
	*size = entry->size;
	return ENTRY_DATA(entry);
}

static void editor_cache_add(unsigned long long key, unsigned int format, const void *data, int size)
{
	if (size <= 0 || cache_bytes + (size_t)size > CACHE_MAX_BYTES) {
		return;
	}
	CacheEntry *entry = MEM_mallocN(sizeof(CacheEntry) + (size_t)size, "GPUEditorShaderBinary");
	entry->key = key;
	entry->format = format;
	entry->size = size;
	memcpy(entry + 1, data, (size_t)size);
	/* A binary the driver rejected is replaced by the new one. */
	entry_put(entry);
	cache_dirty = true;
}

static void editor_cache_dir(char *dir, size_t dir_len)
{
#ifdef _WIN32
	const char *base = getenv("LOCALAPPDATA");
	if (base && base[0]) {
		BLI_join_dirfile(dir, dir_len, base, "AnastacioEngine\\ShaderCache");
		return;
	}
#else
	const char *base = getenv("XDG_CACHE_HOME");
	if (base && base[0]) {
		BLI_join_dirfile(dir, dir_len, base, "AnastacioEngine/ShaderCache");
		return;
	}
	base = getenv("HOME");
	if (base && base[0]) {
		BLI_join_dirfile(dir, dir_len, base, ".cache/AnastacioEngine/ShaderCache");
		return;
	}
#endif
	dir[0] = '\0';
}

static void editor_cache_read(void)
{
	FILE *file = BLI_fopen(cache_path, "rb");
	if (!file) {
		return;
	}
	char head[8];
	unsigned long long device;
	if (fread(head, 1, 8, file) == 8 && memcmp(head, cache_magic, 8) == 0 && fread(&device, 8, 1, file) == 1 &&
	    device == cache_device)
	{
		unsigned long long key;
		unsigned int format;
		int size;
		while (fread(&key, 8, 1, file) == 1 && fread(&format, 4, 1, file) == 1 && fread(&size, 4, 1, file) == 1) {
			if (size <= 0 || cache_bytes + (size_t)size > CACHE_MAX_BYTES) {
				break;
			}
			CacheEntry *entry = MEM_mallocN(sizeof(CacheEntry) + (size_t)size, "GPUEditorShaderBinary");
			entry->key = key;
			entry->format = format;
			entry->size = size;
			if (fread(entry + 1, 1, (size_t)size, file) != (size_t)size) {
				MEM_freeN(entry);
				break;
			}
			entry_put(entry);
		}
	}
	/* Another GPU/driver: its binaries are useless, the file is rewritten with this one's. */
	fclose(file);
}

static void editor_cache_write(void)
{
	char dir[FILE_MAX], tmp_path[FILE_MAX];
	BLI_split_dir_part(cache_path, dir, sizeof(dir));
	BLI_dir_create_recursive(dir);
	BLI_snprintf(tmp_path, sizeof(tmp_path), "%s.tmp", cache_path);

	FILE *file = BLI_fopen(tmp_path, "wb");
	if (!file) {
		return;
	}
	bool ok = fwrite(cache_magic, 1, 8, file) == 8 && fwrite(&cache_device, 8, 1, file) == 1;
	GHashIterator iter;
	GHASH_ITER (iter, cache_entries) {
		const CacheEntry *entry = BLI_ghashIterator_getValue(&iter);
		ok = ok && fwrite(&entry->key, 8, 1, file) == 1 && fwrite(&entry->format, 4, 1, file) == 1 &&
		     fwrite(&entry->size, 4, 1, file) == 1 &&
		     fwrite(ENTRY_DATA(entry), 1, (size_t)entry->size, file) == (size_t)entry->size;
	}
	ok = (fclose(file) == 0) && ok;
	if (ok) {
		if (BLI_exists(cache_path)) {
			BLI_delete(cache_path, false, false);
		}
		ok = BLI_rename(tmp_path, cache_path) == 0;
	}
	if (!ok) {
		BLI_delete(tmp_path, false, false);
		fprintf(stderr, "GPU: could not write the editor shader cache %s\n", cache_path);
	}
}

void GPU_shader_editor_cache_init(void)
{
	if (cache_entries) {
		return;
	}
	const char *disabled = getenv("RANGE_NO_EDITOR_SHADER_CACHE");
	if (disabled && disabled[0] && disabled[0] != '0') {
		return;
	}
	/* Needs a current GL context: the key names the GPU and driver. 0 when program binaries are unsupported. */
	cache_device = GPU_shader_binary_device_key();
	if (!cache_device) {
		return;
	}
	char dir[FILE_MAX];
	editor_cache_dir(dir, sizeof(dir));
	if (!dir[0]) {
		return;
	}
	BLI_join_dirfile(cache_path, sizeof(cache_path), dir, "editor.shaders");

	cache_entries = BLI_ghash_new(entry_hash, entry_cmp, "GPUEditorShaderCache");
	cache_bytes = 0;
	cache_dirty = false;
	editor_cache_read();
	GPU_shader_binary_cache_default_set(editor_cache_find, editor_cache_add);
}

void GPU_shader_editor_cache_save(void)
{
	if (cache_entries && cache_dirty) {
		editor_cache_write();
		cache_dirty = false;
	}
}

void GPU_shader_editor_cache_exit(void)
{
	if (!cache_entries) {
		return;
	}
	GPU_shader_editor_cache_save();
	GPU_shader_binary_cache_default_set(NULL, NULL);
	BLI_ghash_free(cache_entries, NULL, MEM_freeN);
	cache_entries = NULL;
	cache_bytes = 0;
}
