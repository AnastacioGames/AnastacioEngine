/* Standalone test of the Mind Map .mm reader and writer.
 * Build: cl /nologo /W3 /DMM_STANDALONE_TEST /I<space_mindmap> test_mindmap_tree.c <space_mindmap>\mindmap_tree.c */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "mindmap_tree.h"

static int failures = 0;

#define CHECK(cond) \
	do { \
		if (!(cond)) { \
			printf("FAIL line %d: %s\n", __LINE__, #cond); \
			failures++; \
		} \
	} while (0)

static int text_is(const MMElem *node, const char *expected)
{
	char *text = mm_node_text(node);
	const int same = text && strcmp(text, expected) == 0;
	mm_str_free(text);
	return same;
}

static MMDoc *parse(const char *src)
{
	return mm_parse(src, strlen(src), NULL, 0);
}

static const char *freemind_map =
"<map version=\"1.0.1\">\n"
"<!-- To view this file, download free mind mapping software FreeMind -->\n"
"<node CREATED=\"1\" ID=\"ID_1\" MODIFIED=\"2\" TEXT=\"Jogo &#xe1;gua &amp; fogo\">\n"
"<node FOLDED=\"true\" ID=\"ID_2\" POSITION=\"right\" TEXT=\"Motor\">\n"
"<icon BUILTIN=\"idea\"/>\n"
"<font BOLD=\"true\" NAME=\"SansSerif\" SIZE=\"12\"/>\n"
"<node ID=\"ID_3\" TEXT=\"F&#xed;sica\"/>\n"
"</node>\n"
"<node ID=\"ID_4\" POSITION=\"left\" TEXT=\"Fases\">\n"
"<richcontent TYPE=\"NOTE\"><html>\n  <body>\n    <p>Nota &nbsp;<b>forte</b> x</p>\n  </body>\n</html>\n</richcontent>\n"
"<arrowlink DESTINATION=\"ID_2\" ENDARROW=\"Default\"/>\n"
"</node>\n"
"</node>\n"
"</map>\n";

static void test_read(void)
{
	MMDoc *doc = parse(freemind_map);
	MMElem *root, *motor, *fases;

	CHECK(doc != NULL);
	if (!doc) {
		return;
	}
	root = mm_root_node(doc);
	CHECK(text_is(root, "Jogo \xC3\xA1gua & fogo"));
	motor = mm_node_first_child(root);
	CHECK(text_is(motor, "Motor"));
	CHECK(mm_node_folded(motor));
	CHECK(text_is(mm_node_first_child(motor), "F\xC3\xADsica"));
	fases = mm_node_next(motor);
	CHECK(text_is(fases, "Fases"));
	CHECK(!mm_node_folded(fases));
	CHECK(mm_node_next(fases) == NULL);
	mm_free(doc);
}

static void test_round_trip(void)
{
	MMDoc *a = parse(freemind_map), *b;
	char *first, *second;

	CHECK(a != NULL);
	if (!a) {
		return;
	}
	first = mm_write(a, NULL);
	b = parse(first);
	CHECK(b != NULL);
	second = b ? mm_write(b, NULL) : NULL;
	CHECK(second && strcmp(first, second) == 0);
	CHECK(strstr(first, "&#xe1;gua &amp; fogo") != NULL);
	CHECK(strstr(first, "<html>\n  <body>\n    <p>Nota &nbsp;<b>forte</b> x</p>\n  </body>\n</html>\n</richcontent>") != NULL);
	CHECK(strstr(first, "<icon BUILTIN=\"idea\"/>") != NULL);
	CHECK(strstr(first, "<arrowlink DESTINATION=\"ID_2\" ENDARROW=\"Default\"/>") != NULL);
	CHECK(strstr(first, "CREATED=\"1\" ID=\"ID_1\" MODIFIED=\"2\"") != NULL);
	CHECK(strstr(first, "To view this file") != NULL);
	mm_str_free(first);
	mm_str_free(second);
	mm_free(a);
	mm_free(b);
}

static void test_edit(void)
{
	MMDoc *doc = mm_new("Centro");
	MMElem *root = mm_root_node(doc);
	MMElem *a = mm_node_add_child(root, "A <&> \"q\"\nlinha \xC3\xA7");
	MMElem *b = mm_node_add_sibling(a, "B");
	MMElem *c = mm_node_add_child(root, "C");
	MMDoc *back;
	char *out;

	CHECK(mm_node_add_sibling(root, "x") == NULL);
	CHECK(mm_node_remove(root) == 0);
	mm_node_folded_set(b, 1);
	CHECK(mm_node_folded(b));
	mm_node_folded_set(b, 0);
	CHECK(!mm_node_folded(b));
	mm_node_folded_set(b, 1);
	mm_node_add_child(c, "filho");
	CHECK(mm_node_next(a) == b);
	CHECK(mm_node_next(b) == c);

	out = mm_write(doc, NULL);
	back = parse(out);
	CHECK(back != NULL);
	if (back) {
		MMElem *ra = mm_node_first_child(mm_root_node(back));
		CHECK(text_is(ra, "A <&> \"q\"\nlinha \xC3\xA7"));
		CHECK(mm_node_folded(mm_node_next(ra)));
	}
	mm_str_free(out);
	mm_free(back);

	CHECK(mm_node_remove(b) == 1);
	CHECK(mm_node_next(a) == c);
	CHECK(mm_node_remove(c) == 1);
	CHECK(mm_node_next(a) == NULL);
	CHECK(mm_root_node(doc)->last == a);
	mm_free(doc);
}

static void test_escapes(void)
{
	MMDoc *doc = parse(
	        "\xEF\xBB\xBF<?xml version=\"1.0\"?>\n<map><node TEXT='diz \"oi\" &#128512; &#0; &foo; &#xZZ;'/></map>");
	CHECK(doc != NULL);
	if (doc) {
		char *out = mm_write(doc, NULL);
		CHECK(text_is(mm_root_node(doc), "diz \"oi\" \xF0\x9F\x98\x80 &#0; &foo; &#xZZ;"));
		CHECK(strstr(out, "TEXT=\"diz &quot;oi&quot;") != NULL);
		mm_str_free(out);
		mm_free(doc);
	}
}

static void expect_error(const char *src, const char *fragment)
{
	char err[128] = "";
	MMDoc *doc = mm_parse(src, strlen(src), err, sizeof(err));

	CHECK(doc == NULL);
	if (doc == NULL && strstr(err, fragment) == NULL) {
		printf("FAIL error for [%s]: got [%s]\n", src, err);
		failures++;
	}
	mm_free(doc);
}

static void test_invalid(void)
{
	char *deep;
	size_t i, n;

	expect_error("", "not <map>");
	expect_error("<x><node TEXT=\"a\"/></x>", "not <map>");
	expect_error("<map/>", "no root node");
	expect_error("<map><node TEXT=\"a\">", "end of file");
	expect_error("<map><node TEXT=\"a\"></map></node>", "does not match");
	expect_error("<map>\n\n<node TEXT=a/></map>", "Line 3");
	expect_error("<map><node TEXT=\"a/></map>", "attribute");
	expect_error("<map><node TEXT=\"a\"/></map><map/>", "More than one");
	expect_error("oi<map><node TEXT=\"a\"/></map>", "outside");
	expect_error("<map><!-- x <node TEXT=\"a\"/></map>", "comment");
	expect_error("<map><node TEXT=\"a\"/></map></map>", "does not match");

	n = 2000;
	deep = malloc(n * 6 + 16);
	strcpy(deep, "<map>");
	for (i = 0; i < n; i++) {
		memcpy(deep + 5 + i * 6, "<node>", 6);
	}
	deep[5 + n * 6] = '\0';
	expect_error(deep, "too deeply");
	free(deep);
}

static void test_not_terminated(void)
{
	const char src[] = "<map><node TEXT=\"a\"/></map>XXXX";
	MMDoc *doc = mm_parse(src, sizeof(src) - 5, NULL, 0);

	CHECK(doc != NULL);
	mm_free(doc);
}

static void test_move(void)
{
	MMDoc *doc = mm_new("R");
	MMElem *root = mm_root_node(doc);
	MMElem *a = mm_node_add_child(root, "a");
	MMElem *b = mm_node_add_child(root, "b");
	MMElem *c = mm_node_add_child(a, "c");

	CHECK(mm_node_move(root, a, NULL) == 0);
	CHECK(mm_node_move(a, c, NULL) == 0);
	CHECK(mm_node_move(a, a, NULL) == 0);
	CHECK(mm_node_first_child(a) == c && mm_node_next(a) == b);

	CHECK(mm_node_move(b, root, a) == 1);
	CHECK(mm_node_first_child(root) == b && mm_node_next(b) == a && mm_node_next(a) == NULL);
	CHECK(root->last == a && b->prev == NULL);
	CHECK(mm_node_move(c, b, NULL) == 1);
	CHECK(mm_node_first_child(a) == NULL && c->parent == b);
	CHECK(mm_node_move(b, root, b) == 1);
	mm_free(doc);
}

static void test_icon_note(void)
{
	MMDoc *doc = parse(freemind_map);
	MMElem *root = mm_root_node(doc);
	MMElem *motor = mm_node_first_child(root);
	MMElem *fases = mm_node_next(motor);
	MMDoc *back;
	char *s, *out;

	s = mm_node_icon(motor);
	CHECK(s && strcmp(s, "idea") == 0);
	mm_str_free(s);
	s = mm_node_note(fases);
	CHECK(s && strcmp(s, "Nota forte x") == 0);
	mm_str_free(s);
	CHECK(mm_node_note(motor) == NULL && !mm_node_has_note(motor));

	mm_node_icon_set(motor, "flag");
	mm_node_note_set(motor, "a < b & \xC3\xA7");
	mm_node_note_set(fases, NULL);
	CHECK(!mm_node_has_note(fases));
	out = mm_write(doc, NULL);
	back = parse(out);
	CHECK(back != NULL);
	if (back) {
		MMElem *m = mm_node_first_child(mm_root_node(back));
		s = mm_node_note(m);
		CHECK(s && strcmp(s, "a < b & \xC3\xA7") == 0);
		mm_str_free(s);
		s = mm_node_icon(m);
		CHECK(s && strcmp(s, "flag") == 0);
		mm_str_free(s);
		mm_node_icon_set(m, NULL);
		s = mm_node_icon(m);
		CHECK(s == NULL);
		mm_free(back);
	}
	mm_str_free(out);
	mm_free(doc);
}

static void test_copy_into(void)
{
	MMDoc *from = parse("<map><node ID=\"A\" TEXT=\"R\"><node ID=\"B\" TEXT=\"x &amp; y\" COLOR=\"#ff0000\">"
	                    "<icon BUILTIN=\"idea\"/><node ID=\"C\" TEXT=\"f\"/></node></node></map>");
	MMDoc *to = mm_new("Destino");
	MMElem *copy = mm_node_copy_into(mm_node_first_child(mm_root_node(from)), mm_root_node(to));
	char *value;

	mm_free(from);
	CHECK(text_is(copy, "x & y") && text_is(mm_node_first_child(copy), "f"));
	value = mm_attr_get(copy, "COLOR");
	CHECK(value && strcmp(value, "#ff0000") == 0);
	mm_str_free(value);
	value = mm_attr_get(copy, "ID");
	CHECK(value == NULL);
	mm_str_free(value);
	value = mm_attr_get(mm_node_first_child(copy), "ID");
	CHECK(value == NULL);
	mm_str_free(value);
	value = mm_node_icon(copy);
	CHECK(value && strcmp(value, "idea") == 0);
	mm_str_free(value);
	mm_free(to);
}

int main(void)
{
	test_copy_into();
	test_read();
	test_round_trip();
	test_edit();
	test_escapes();
	test_invalid();
	test_not_terminated();
	test_move();
	test_icon_note();
	printf(failures ? "%d FALHA(S)\n" : "TODOS OK\n", failures);
	return failures != 0;
}
