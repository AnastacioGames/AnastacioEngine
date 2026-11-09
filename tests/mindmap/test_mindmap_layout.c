/* Standalone test of the Mind Map layout.
 * Build: cl /nologo /W3 /DMM_STANDALONE_TEST /I<space_mindmap> test_mindmap_layout.c
 *        <space_mindmap>\mindmap_layout.c <space_mindmap>\mindmap_tree.c */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "mindmap_layout.h"
#include "mindmap_tree.h"

static int failures = 0;

#define CHECK(cond) \
	do { \
		if (!(cond)) { \
			printf("FAIL line %d: %s\n", __LINE__, #cond); \
			failures++; \
		} \
	} while (0)

static float fake_width(const char *text, void *UNUSED_data)
{
	(void)UNUSED_data;
	return (float)strlen(text) * 10.0f;
}

static MMLayout *layout_of(const char *src, MMDoc **r_doc)
{
	*r_doc = mm_parse(src, strlen(src), NULL, 0);
	CHECK(*r_doc != NULL);
	return *r_doc ? mm_layout_build(*r_doc, fake_width, NULL) : NULL;
}

static int find(const MMLayout *l, const char *text)
{
	int i;

	for (i = 0; i < l->count; i++) {
		if (strcmp(l->nodes[i].text, text) == 0) {
			return i;
		}
	}
	return -1;
}

static void test_sides_and_fold(void)
{
	MMDoc *doc;
	MMLayout *l = layout_of(
	        "<map><node TEXT=\"Meu jogo\">"
	        "<node POSITION=\"right\" TEXT=\"Motor\"><node TEXT=\"Fisica\"/><node TEXT=\"Render\"/></node>"
	        "<node POSITION=\"left\" FOLDED=\"true\" TEXT=\"Fases\"><node TEXT=\"Chefes\"/></node>"
	        "</node></map>", &doc);
	const MMLayoutNode *root, *motor, *fisica, *render, *fases;

	CHECK(l && l->count == 5);
	if (!l || l->count != 5) {
		return;
	}
	root = &l->nodes[0];
	motor = &l->nodes[find(l, "Motor")];
	fisica = &l->nodes[find(l, "Fisica")];
	render = &l->nodes[find(l, "Render")];
	fases = &l->nodes[find(l, "Fases")];

	CHECK(root->xmin == -root->xmax && root->parent == -1);
	CHECK(motor->side == 1 && motor->xmin > root->xmax);
	CHECK(fases->side == -1 && fases->xmax < root->xmin);
	CHECK(fases->has_hidden_children && !motor->has_hidden_children);
	CHECK(find(l, "Chefes") == -1);
	CHECK(fisica->xmin > motor->xmax && fisica->ymin > render->ymax);
	CHECK(motor->ymax + motor->ymin == fisica->ymin + render->ymax);
	CHECK(l->xmin == fases->xmin && l->xmax == fisica->xmax);
	mm_layout_free(l);
	mm_free(doc);
}

static void test_no_overlap(void)
{
	MMDoc *doc = mm_new("Centro");
	MMElem *root = mm_root_node(doc);
	MMLayout *l;
	int i, j, k, overlaps = 0;

	for (i = 0; i < 10; i++) {
		MMElem *a = mm_node_add_child(root, "ramo");

		if (i & 1) {
			mm_attr_set(a, "POSITION", "left");
		}
		for (j = 0; j < 10; j++) {
			MMElem *b = mm_node_add_child(a, "sub");

			for (k = 0; k < 9; k++) {
				mm_node_add_child(b, "folha com texto");
			}
		}
	}
	l = mm_layout_build(doc, fake_width, NULL);
	CHECK(l->count == 1 + 10 + 100 + 900);
	for (i = 0; i < l->count; i++) {
		const MMLayoutNode *a = &l->nodes[i];

		CHECK(a->parent < i);
		for (j = i + 1; j < l->count; j++) {
			const MMLayoutNode *b = &l->nodes[j];

			if (a->xmin < b->xmax && b->xmin < a->xmax && a->ymin < b->ymax && b->ymin < a->ymax) {
				overlaps++;
			}
		}
	}
	CHECK(overlaps == 0);
	mm_layout_free(l);
	mm_free(doc);
}

static void test_text_cleanup(void)
{
	char src[800] = "<map><node TEXT=\"linha&#10;dois\"><node TEXT=\"";
	MMDoc *doc;
	MMLayout *l;
	int i;

	for (i = 0; i < 100; i++) {
		strcat(src, "\xC3\xA7");
	}
	strcat(src, "\"/><node><richcontent TYPE=\"NODE\"><html/></richcontent></node></node></map>");
	l = layout_of(src, &doc);
	CHECK(l && l->count == 3);
	if (l && l->count == 3) {
		CHECK(strcmp(l->nodes[0].text, "linha dois") == 0);
		CHECK(strlen(l->nodes[1].text) <= 80);
		CHECK(strcmp(l->nodes[1].text + strlen(l->nodes[1].text) - 5, "\xC3\xA7...") == 0);
		CHECK(strcmp(l->nodes[2].text, "...") == 0);
	}
	mm_layout_free(l);
	mm_free(doc);
}

static void test_tasks_and_link(void)
{
	MMDoc *doc;
	MMLayout *l = layout_of(
	        "<map><node TEXT=\"R\">"
	        "<node TEXT=\"A\" ANASTACIO_LINK=\"OBCube\" FOLDED=\"true\">"
	        "<node TEXT=\"B\" ANASTACIO_TASK=\"done\"/><node TEXT=\"C\" ANASTACIO_TASK=\"todo\"/></node>"
	        "<node TEXT=\"D\" ANASTACIO_TASK=\"todo\" ANASTACIO_ICON=\"MESH_CUBE\"/>"
	        "</node></map>", &doc);

	CHECK(l && l->count == 3);
	if (l && l->count == 3) {
		const MMLayoutNode *a = &l->nodes[find(l, "A")], *d = &l->nodes[find(l, "D")];

		CHECK(strcmp(l->nodes[0].progress, "1/3") == 0);
		CHECK(strcmp(a->progress, "1/2") == 0 && a->has_link && a->task == MM_TASK_NONE);
		CHECK(d->progress[0] == '\0' && !d->has_link && d->task == MM_TASK_TODO);
		CHECK(strcmp(d->engine_icon, "MESH_CUBE") == 0 && a->engine_icon[0] == '\0');
		CHECK(d->text_offset == 32.0f);
	}
	mm_layout_free(l);
	mm_free(doc);
}

int main(void)
{
	test_tasks_and_link();
	test_sides_and_fold();
	test_no_overlap();
	test_text_cleanup();
	printf(failures ? "%d FALHA(S)\n" : "TODOS OK\n", failures);
	return failures != 0;
}
