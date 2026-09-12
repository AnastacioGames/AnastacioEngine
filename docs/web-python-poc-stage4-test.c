/* Etapa 4 da PoC (docs/web-python-poc-plan.md): callback por frame via
 * emscripten_set_main_loop, Python inicializado uma unica vez (nao por
 * frame), com round-trip bidirecional: C chama update(dt, input) em
 * Python; Python chama de volta uma funcao C exposta (stage4_engine.
 * set_position) para atualizar uma posicao — simula o padrao real do BGE
 * (engine chama script, script chama API da engine).
 *
 * Estado persistente vive em uma struct estatica (nao em variavel local de
 * main), para nao capturar ponteiro que sai de escopo no callback
 * assincrono (ver docs/web-integration-audit.md, secao 3). */

#include <Python.h>
#include <emscripten.h>
#include <stdio.h>

typedef struct {
    PyObject *game_logic_module;
    PyObject *update_func;
    double position;
    int frame_count;
    int input_left;
    int input_right;
} Stage4State;

static Stage4State g_state;

/* --- API exposta ao Python como modulo "stage4_engine" --- */

static PyObject *engine_set_position(PyObject *self, PyObject *args) {
    double value;
    if (!PyArg_ParseTuple(args, "d", &value)) {
        return NULL;
    }
    g_state.position = value;
    Py_RETURN_NONE;
}

static PyMethodDef stage4_engine_methods[] = {
    {"set_position", engine_set_position, METH_VARARGS,
     "Atualiza a posicao mantida pelo lado C (API da engine)."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef stage4_engine_module = {
    PyModuleDef_HEAD_INIT, "stage4_engine", NULL, -1, stage4_engine_methods,
    NULL, NULL, NULL, NULL
};

static PyObject *PyInit_stage4_engine(void) {
    return PyModule_Create(&stage4_engine_module);
}

/* --- callback de frame --- */

static void main_loop_iter(void) {
    PyObject *args, *result;

    if (g_state.frame_count >= 180) {
        printf("STAGE4_OK frames=%d posicao_final=%f\n", g_state.frame_count,
               g_state.position);
        emscripten_cancel_main_loop();
        Py_Finalize();
        return;
    }

    /* Padrao de input determinístico, sem depender de teclado real: move
     * para a direita nos primeiros 90 frames, para a esquerda depois. */
    g_state.input_left = (g_state.frame_count >= 90) ? 1 : 0;
    g_state.input_right = (g_state.frame_count < 90) ? 1 : 0;

    if (g_state.frame_count == 89) {
        printf("STAGE4_MEIO_CAMINHO frame=%d posicao=%f\n",
               g_state.frame_count, g_state.position);
    }

    args = Py_BuildValue("(dii)", 1.0 / 60.0, g_state.input_left,
                          g_state.input_right);
    result = PyObject_CallObject(g_state.update_func, args);
    Py_DECREF(args);

    if (result == NULL) {
        fprintf(stderr, "ERRO: update() falhou no frame %d\n",
                g_state.frame_count);
        PyErr_Print();
        emscripten_cancel_main_loop();
        Py_Finalize();
        return;
    }
    Py_DECREF(result);

    g_state.frame_count++;
}

int main(void) {
    PyObject *sys_module, *path_list, *assets_path;

    if (PyImport_AppendInittab("stage4_engine", &PyInit_stage4_engine) != 0) {
        fprintf(stderr, "ERRO: PyImport_AppendInittab falhou\n");
        return 1;
    }

    Py_InitializeEx(0);
    if (!Py_IsInitialized()) {
        fprintf(stderr, "ERRO: Py_Initialize falhou\n");
        return 1;
    }

    sys_module = PyImport_ImportModule("sys");
    if (sys_module == NULL) {
        PyErr_Print();
        Py_Finalize();
        return 1;
    }
    path_list = PyObject_GetAttrString(sys_module, "path");
    assets_path = PyUnicode_FromString("/assets");
    PyList_Append(path_list, assets_path);
    Py_DECREF(assets_path);
    Py_DECREF(path_list);
    Py_DECREF(sys_module);

    g_state.game_logic_module = PyImport_ImportModule("game_logic");
    if (g_state.game_logic_module == NULL) {
        fprintf(stderr, "ERRO: falha ao importar game_logic\n");
        PyErr_Print();
        Py_Finalize();
        return 1;
    }

    g_state.update_func = PyObject_GetAttrString(g_state.game_logic_module,
                                                  "update");
    if (g_state.update_func == NULL) {
        fprintf(stderr, "ERRO: game_logic.update nao encontrado\n");
        PyErr_Print();
        Py_Finalize();
        return 1;
    }

    g_state.position = 0.0;
    g_state.frame_count = 0;

    printf("STAGE4_INIT_OK aguardando frames...\n");

    /* fps=0 -> usa requestAnimationFrame do navegador; simulate_infinite=1
     * -> nao pode haver codigo bloqueante apos esta chamada, o controle
     * volta ao navegador entre frames. */
    emscripten_set_main_loop(main_loop_iter, 0, 1);

    return 0;
}
