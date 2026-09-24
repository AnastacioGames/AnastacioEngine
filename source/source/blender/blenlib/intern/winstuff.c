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
 *
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 * Windows-posix compatibility layer, windows-specific functions.
 */

/** \file blender/blenlib/intern/winstuff.c
 *  \ingroup bli
 */


#ifdef WIN32

#include <stdlib.h>
#include <stdio.h>
#include <conio.h>

#include "MEM_guardedalloc.h"

#define WIN32_SKIP_HKEY_PROTECTION      // need to use HKEY
#include "BLI_winstuff.h"
#include "BLI_utildefines.h"
#include "BLI_path_util.h"
#include "BLI_string.h"

#include "../blenkernel/BKE_global.h"  /* G.background, bad level include (no function calls) */

#include "utf_winfunc.h"
#include "utfconv.h"

/* FILE_MAXDIR + FILE_MAXFILE */

int BLI_getInstallationDir(char *str)
{
	char dir[FILE_MAXDIR];
	int a;
	/*change to utf support*/
	GetModuleFileName(NULL, str, FILE_MAX);
	BLI_split_dir_part(str, dir, sizeof(dir)); /* shouldn't be relative */
	a = strlen(dir);
	if (dir[a - 1] == '\\') dir[a - 1] = 0;

	strcpy(str, dir);

	return 1;
}

static void file_extensions_fail(HKEY root)
{
	printf("failed\n");
	if (root)
		RegCloseKey(root);
	if (!G.background)
		MessageBox(0, "Could not register Range file associations.", "Range Engine error", MB_OK | MB_ICONERROR);
	TerminateProcess(GetCurrentProcess(), 1);
}

static bool registry_set_default(HKEY root, const char *key_name, const char *value)
{
	LONG lresult;
	HKEY hkey;
	DWORD dwd = 0;

	lresult = RegCreateKeyEx(root, key_name, 0, NULL, REG_OPTION_NON_VOLATILE, KEY_WRITE, NULL, &hkey, &dwd);
	if (lresult != ERROR_SUCCESS)
		return false;

	lresult = RegSetValueEx(hkey, NULL, 0, REG_SZ, (const BYTE *)value, (DWORD)strlen(value) + 1);
	RegCloseKey(hkey);
	return lresult == ERROR_SUCCESS;
}

static bool register_file_association(HKEY root,
	                                  const char *extension,
	                                  const char *prog_id,
	                                  const char *description,
	                                  const char *executable,
	                                  const int icon_index)
{
	char command_key[MAX_PATH];
	char icon_key[MAX_PATH];
	char command[MAX_PATH * 2 + 8];
	char icon[MAX_PATH + 8];

	if (BLI_snprintf(command_key, sizeof(command_key), "%s\\shell\\open\\command", prog_id) >= (int)sizeof(command_key) ||
	    BLI_snprintf(icon_key, sizeof(icon_key), "%s\\DefaultIcon", prog_id) >= (int)sizeof(icon_key) ||
	    BLI_snprintf(command, sizeof(command), "\"%s\" \"%%1\"", executable) >= (int)sizeof(command) ||
	    BLI_snprintf(icon, sizeof(icon), "\"%s\", %d", executable, icon_index) >= (int)sizeof(icon)) {
		return false;
	}

	return registry_set_default(root, prog_id, description) &&
	       registry_set_default(root, command_key, command) &&
	       registry_set_default(root, icon_key, icon) &&
	       registry_set_default(root, extension, prog_id);
}

static bool path_set_filename(char *path, const char *filename)
{
	char *separator = strrchr(path, '\\');
	if (separator == NULL || (size_t)(separator - path + 1) + strlen(filename) + 1 > MAX_PATH) {
		return false;
	}

	BLI_strncpy(separator + 1, filename, MAX_PATH - (size_t)(separator - path + 1));
	return true;
}

void BLI_windows_register_file_extensions(void)
{
	LONG lresult;
	HKEY root = NULL;
	BOOL user_mode = false;
	DWORD engine_path_length;
	char engine_path[MAX_PATH];
	char runtime_path[MAX_PATH];
	char message[256];

	printf("Registering Range file associations...");
	engine_path_length = GetModuleFileName(NULL, engine_path, sizeof(engine_path));
	if (engine_path_length == 0 || engine_path_length >= sizeof(engine_path)) {
		file_extensions_fail(NULL);
	}
	BLI_strncpy(runtime_path, engine_path, sizeof(runtime_path));
	if (!path_set_filename(runtime_path, "RangeRuntime.exe")) {
		file_extensions_fail(NULL);
	}

	/* Prefer a machine-wide association; use the current user's classes when not elevated. */
	lresult = RegOpenKeyEx(HKEY_LOCAL_MACHINE, "Software\\Classes", 0, KEY_WRITE, &root);
	if (lresult != ERROR_SUCCESS) {
		user_mode = true;
		lresult = RegOpenKeyEx(HKEY_CURRENT_USER, "Software\\Classes", 0, KEY_WRITE, &root);
		if (lresult != ERROR_SUCCESS) {
			file_extensions_fail(NULL);
		}
	}

	if (!register_file_association(root, ".blend", "RangeEngine.BlendFile", "Range Engine Blend File", engine_path, 1) ||
	    !register_file_association(root, ".range", "RangeEngine.RangeFile", "Range Engine Game", runtime_path, 0)) {
		file_extensions_fail(root);
	}

	RegCloseKey(root);
	printf("success (%s)\n", user_mode ? "user" : "system");
	if (!G.background) {
		BLI_snprintf(message, sizeof(message), "Range file associations registered for %s.",
		             user_mode ? "the current user. Run as administrator to register for all users" : "all users");
		MessageBox(NULL, message, "Range Engine", MB_OK | MB_ICONINFORMATION);
	}
	TerminateProcess(GetCurrentProcess(), 0);
}

static void unregister_file_association(HKEY root, const char *extension, const char *prog_id)
{
	HKEY hkey;
	DWORD type;
	DWORD size = 64;
	char value[64];
	char command_key[MAX_PATH];
	char open_key[MAX_PATH];
	char shell_key[MAX_PATH];
	char icon_key[MAX_PATH];

	if (RegOpenKeyEx(root, extension, 0, KEY_QUERY_VALUE | KEY_SET_VALUE, &hkey) == ERROR_SUCCESS) {
		if (RegQueryValueEx(hkey, NULL, NULL, &type, (BYTE *)value, &size) == ERROR_SUCCESS &&
		    type == REG_SZ && strcmp(value, prog_id) == 0) {
			RegDeleteValue(hkey, NULL);
		}
		RegCloseKey(hkey);
		RegDeleteKey(root, extension); /* only succeeds if the key is now empty */
	}

	BLI_snprintf(command_key, sizeof(command_key), "%s\\shell\\open\\command", prog_id);
	BLI_snprintf(open_key, sizeof(open_key), "%s\\shell\\open", prog_id);
	BLI_snprintf(shell_key, sizeof(shell_key), "%s\\shell", prog_id);
	BLI_snprintf(icon_key, sizeof(icon_key), "%s\\DefaultIcon", prog_id);
	RegDeleteKey(root, command_key);
	RegDeleteKey(root, open_key);
	RegDeleteKey(root, shell_key);
	RegDeleteKey(root, icon_key);
	RegDeleteKey(root, prog_id);
}

void BLI_windows_unregister_file_extensions(void)
{
	HKEY root;

	printf("Removing Range file associations...");
	/* Try both stores: an elevated registration lives in HKLM, a regular one in HKCU. */
	if (RegOpenKeyEx(HKEY_CURRENT_USER, "Software\\Classes", 0, KEY_WRITE, &root) == ERROR_SUCCESS) {
		unregister_file_association(root, ".blend", "RangeEngine.BlendFile");
		unregister_file_association(root, ".range", "RangeEngine.RangeFile");
		RegCloseKey(root);
	}
	if (RegOpenKeyEx(HKEY_LOCAL_MACHINE, "Software\\Classes", 0, KEY_WRITE, &root) == ERROR_SUCCESS) {
		unregister_file_association(root, ".blend", "RangeEngine.BlendFile");
		unregister_file_association(root, ".range", "RangeEngine.RangeFile");
		RegCloseKey(root);
	}

	printf("success\n");
	if (!G.background) {
		MessageBox(NULL, "Range file associations removed.", "Range Engine", MB_OK | MB_ICONINFORMATION);
	}
	TerminateProcess(GetCurrentProcess(), 0);
}

void get_default_root(char *root)
{
	char str[MAX_PATH + 1];

	/* the default drive to resolve a directory without a specified drive
	 * should be the Windows installation drive, since this was what the OS
	 * assumes. */
	if (GetWindowsDirectory(str, MAX_PATH + 1)) {
		root[0] = str[0];
		root[1] = ':';
		root[2] = '\\';
		root[3] = '\0';
	}
	else {
		/* if GetWindowsDirectory fails, something has probably gone wrong,
		 * we are trying the blender install dir though */
		if (GetModuleFileName(NULL, str, MAX_PATH + 1)) {
			printf("Error! Could not get the Windows Directory - "
			       "Defaulting to Blender installation Dir!\n");
			root[0] = str[0];
			root[1] = ':';
			root[2] = '\\';
			root[3] = '\0';
		}
		else {
			DWORD tmp;
			int i;
			int rc = 0;
			/* now something has gone really wrong - still trying our best guess */
			printf("Error! Could not get the Windows Directory - "
			       "Defaulting to first valid drive! Path might be invalid!\n");
			tmp = GetLogicalDrives();
			for (i = 2; i < 26; i++) {
				if ((tmp >> i) & 1) {
					root[0] = 'a' + i;
					root[1] = ':';
					root[2] = '\\';
					root[3] = '\0';
					if (GetFileAttributes(root) != 0xFFFFFFFF) {
						rc = i;
						break;
					}
				}
			}
			if (0 == rc) {
				printf("ERROR in 'get_default_root': can't find a valid drive!\n");
				root[0] = 'C';
				root[1] = ':';
				root[2] = '\\';
				root[3] = '\0';
			}
		}
	}
}

/* UNUSED */
#if 0
int check_file_chars(char *filename)
{
	char *p = filename;
	while (*p) {
		switch (*p) {
			case ':':
			case '?':
			case '*':
			case '|':
			case '\\':
			case '/':
			case '\"':
				return 0;
				break;
		}

		p++;
	}
	return 1;
}
#endif

#else

/* intentionally empty for UNIX */

#endif
