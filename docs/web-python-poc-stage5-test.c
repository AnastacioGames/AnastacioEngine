/* Etapa 5 da PoC (docs/web-python-poc-plan.md): prova grafica isolada —
 * SDL2 + WebGL desenhando um quadrado, movido pela mesma funcao Python da
 * Etapa 4 (game_logic.update chamando stage4_engine.set_position). Nao
 * toca no RangeRuntime; e so a combinacao das tres tecnologias. */

#include <Python.h>
#include <emscripten.h>
#include <SDL2/SDL.h>
#include <SDL2/SDL_opengles2.h>
#include <stdio.h>

typedef struct {
    PyObject *game_logic_module;
    PyObject *update_func;
    double position;
    int input_left;
    int input_right;
    int frame_count;
    SDL_Window *window;
    SDL_GLContext gl_context;
} Stage5State;

static Stage5State g_state;

static PyObject *engine_set_position(PyObject *self, PyObject *args) {
    double value;
    if (!PyArg_ParseTuple(args, "d", &value)) {
        return NULL;
    }
    g_state.position = value;
    Py_RETURN_NONE;
}

static PyMethodDef stage4_engine_methods[] = {
    {"set_position", engine_set_position, METH_VARARGS, "Atualiza a posicao (API da engine)."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef stage4_engine_module = {
    PyModuleDef_HEAD_INIT, "stage4_engine", NULL, -1, stage4_engine_methods,
    NULL, NULL, NULL, NULL
};

static PyObject *PyInit_stage4_engine(void) {
    return PyModule_Create(&stage4_engine_module);
}

static void handle_keys(void) {
    const Uint8 *keys = SDL_GetKeyboardState(NULL);
    g_state.input_left = keys[SDL_SCANCODE_A] ? 1 : 0;
    g_state.input_right = keys[SDL_SCANCODE_D] ? 1 : 0;
}

static void render_square(void) {
    float x = (float)(g_state.position / 100.0);
    if (x > 1.0f) x = 1.0f;
    if (x < -1.0f) x = -1.0f;

    glClearColor(0.1f, 0.1f, 0.15f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glViewport(0, 0, 640, 480);
    glScissor((GLint)((x + 1.0f) * 0.5f * 640.0f) - 20, 480 / 2 - 20, 40, 40);
    glEnable(GL_SCISSOR_TEST);
    glClearColor(0.9f, 0.6f, 0.1f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glDisable(GL_SCISSOR_TEST);

    SDL_GL_SwapWindow(g_state.window);
}

static void main_loop_iter(void) {
    SDL_Event event;
    PyObject *args, *result;

    while (SDL_PollEvent(&event)) {
        if (event.type == SDL_QUIT) {
            emscripten_cancel_main_loop();
            return;
        }
    }

    handle_keys();

    args = Py_BuildValue("(dii)", 1.0 / 60.0, g_state.input_left, g_state.input_right);
    result = PyObject_CallObject(g_state.update_func, args);
    Py_DECREF(args);

    if (result == NULL) {
        fprintf(stderr, "ERRO: update() falhou no frame %d\n", g_state.frame_count);
        PyErr_Print();
        emscripten_cancel_main_loop();
        return;
    }
    Py_DECREF(result);

    render_square();

    if (g_state.frame_count == 0) {
        printf("STAGE5_FIRST_FRAME_OK posicao=%f\n", g_state.position);
    }
    g_state.frame_count++;

    if (g_state.frame_count == 120) {
        printf("STAGE5_OK frames=%d posicao=%f\n", g_state.frame_count, g_state.position);
    }
}

int main(void) {
    PyObject *sys_module, *path_list, *assets_path;

    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "ERRO: SDL_Init falhou: %s\n", SDL_GetError());
        return 1;
    }

    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 2);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);

    g_state.window = SDL_CreateWindow("stage5", SDL_WINDOWPOS_UNDEFINED,
                                       SDL_WINDOWPOS_UNDEFINED, 640, 480,
                                       SDL_WINDOW_OPENGL);
    if (g_state.window == NULL) {
        fprintf(stderr, "ERRO: SDL_CreateWindow falhou: %s\n", SDL_GetError());
        return 1;
    }

    g_state.gl_context = SDL_GL_CreateContext(g_state.window);
    if (g_state.gl_context == NULL) {
        fprintf(stderr, "ERRO: SDL_GL_CreateContext falhou: %s\n", SDL_GetError());
        return 1;
    }
    printf("STAGE5_GL_CONTEXT_OK versao=%s\n", (const char *)glGetString(GL_VERSION));

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

    g_state.update_func = PyObject_GetAttrString(g_state.game_logic_module, "update");
    if (g_state.update_func == NULL) {
        fprintf(stderr, "ERRO: game_logic.update nao encontrado\n");
        PyErr_Print();
        Py_Finalize();
        return 1;
    }

    g_state.position = 0.0;
    g_state.frame_count = 0;

    emscripten_set_main_loop(main_loop_iter, 0, 1);
    return 0;
}
