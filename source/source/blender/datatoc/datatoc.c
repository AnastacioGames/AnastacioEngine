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
 */

/** \file blender/datatoc/datatoc.c
 *  \ingroup datatoc
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* #define VERBOSE */

#define MAX2(x, y)               ( (x) > (y) ? (x) : (y) )
#define MAX3(x, y, z)             MAX2(MAX2((x), (y)), (z) )

static char *basename(char *string)
{
	char *lfslash, *lbslash;

	lfslash = strrchr(string, '/');
	lbslash = strrchr(string, '\\');
	if (lbslash) lbslash++;
	if (lfslash) lfslash++;

	return MAX3(string, lfslash, lbslash);
}

int main(int argc, char **argv)
{
	FILE *fpin,  *fpout;
	long size;
	int i;
	int argv_len;
	int write_error;

	if (argc != 3) {
		printf("Usage: datatoc <data_file_from> <data_file_to>\n");
		exit(1);
	}

	fpin = fopen(argv[1], "rb");
	if (!fpin) {
		printf("Unable to open input <%s>\n", argv[1]);
		exit(1);
	}

	argv[1] = basename(argv[1]);

	if (fseek(fpin, 0L, SEEK_END) != 0 || (size = ftell(fpin)) < 0) {
		printf("Unable to determine size of input <%s>\n", argv[1]);
		fclose(fpin);
		exit(1);
	}
	if (fseek(fpin, 0L, SEEK_SET) != 0) {
		printf("Unable to rewind input <%s>\n", argv[1]);
		fclose(fpin);
		exit(1);
	}

	if (argv[1][0] == '.') argv[1]++;

#ifdef VERBOSE
	printf("Making C file <%s>\n", argv[2]);
#endif

	argv_len = (int)strlen(argv[1]);
	for (i = 0; i < argv_len; i++)
		if (argv[1][i] == '.') argv[1][i] = '_';

	fpout = fopen(argv[2], "w");
	if (!fpout) {
		fprintf(stderr, "Unable to open output <%s>\n", argv[2]);
		exit(1);
	}

	fprintf(fpout, "/* DataToC output of file <%s> */\n\n", argv[1]);

	/* Quiet 'missing-variable-declarations' warning. */
	fprintf(fpout, "extern int datatoc_%s_size;\n", argv[1]);
	fprintf(fpout, "extern char datatoc_%s[];\n\n", argv[1]);

	fprintf(fpout, "int datatoc_%s_size = %d;\n", argv[1], (int)size);
	fprintf(fpout, "char datatoc_%s[] = {\n", argv[1]);
	while (size--) {
		int byte;

		/* if we want to open in an editor
		 * this is nicer to avoid very long lines */
#ifdef VERBOSE
		if (size % 32 == 31) {
			fprintf(fpout, "\n");
		}
#endif

		byte = getc(fpin);
		if (byte == EOF) {
			fprintf(stderr, "Unexpected end of input <%s>\n", argv[1]);
			fclose(fpin);
			fclose(fpout);
			remove(argv[2]);
			return 1;
		}

		/* fprintf (fpout, "\\x%02x", byte); */
		fprintf(fpout, "%3d,", byte);
	}

	/* trailing NULL terminator, this isnt needed in some cases and
	 * won't be taken into account by the size variable, but its useful when dealing with
	 * NULL terminated string data */
	fprintf(fpout, "0\n};\n\n");

	fclose(fpin);
	write_error = ferror(fpout);
	if (fclose(fpout) != 0) {
		write_error = 1;
	}
	if (write_error) {
		fprintf(stderr, "Unable to write output <%s>\n", argv[2]);
		remove(argv[2]);
		return 1;
	}
	return 0;
}
