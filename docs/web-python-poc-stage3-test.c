/* Etapa 3 da PoC (docs/web-python-poc-plan.md): prova de que import de
 * stdlib (json, math) + modulo externo (game_logic.py) + leitura de
 * arquivo (config.json) funcionam via FS virtual (--preload-file), e que
 * uma excecao controlada produz traceback legivel sem derrubar o processo.
 * Servir via `python3 -m http.server` (ver Etapa 2 sobre por que Node
 * sozinho nao fecha a etapa). */

#include <Python.h>
#include <stdio.h>

static int run_compute_distance(double *out_value) {
    PyObject *sys_module, *path_list, *assets_path;
    PyObject *game_logic, *func, *result, *args;

    sys_module = PyImport_ImportModule("sys");
    if (sys_module == NULL) {
        PyErr_Print();
        return -1;
    }
    path_list = PyObject_GetAttrString(sys_module, "path");
    assets_path = PyUnicode_FromString("/assets");
    PyList_Append(path_list, assets_path);
    Py_DECREF(assets_path);
    Py_DECREF(path_list);
    Py_DECREF(sys_module);

    game_logic = PyImport_ImportModule("game_logic");
    if (game_logic == NULL) {
        fprintf(stderr, "ERRO: falha ao importar game_logic (json/math/arquivo)\n");
        PyErr_Print();
        return -1;
    }

    func = PyObject_GetAttrString(game_logic, "compute_distance");
    if (func == NULL) {
        PyErr_Print();
        Py_DECREF(game_logic);
        return -1;
    }

    args = Py_BuildValue("(s)", "/assets/config.json");
    result = PyObject_CallObject(func, args);
    Py_DECREF(args);

    if (result == NULL) {
        fprintf(stderr, "ERRO: compute_distance falhou\n");
        PyErr_Print();
        Py_DECREF(func);
        Py_DECREF(game_logic);
        return -1;
    }

    *out_value = PyFloat_AsDouble(result);
    Py_DECREF(result);
    Py_DECREF(func);
    Py_DECREF(game_logic);

    if (PyErr_Occurred()) {
        PyErr_Print();
        return -1;
    }
    return 0;
}

static int run_controlled_exception(void) {
    PyObject *game_logic, *func, *result;

    game_logic = PyImport_ImportModule("game_logic");
    if (game_logic == NULL) {
        PyErr_Print();
        return -1;
    }

    func = PyObject_GetAttrString(game_logic, "trigger_controlled_exception");
    if (func == NULL) {
        PyErr_Print();
        Py_DECREF(game_logic);
        return -1;
    }

    result = PyObject_CallObject(func, NULL);
    Py_DECREF(func);
    Py_DECREF(game_logic);

    if (result == NULL) {
        /* Esperado: a excecao deve aparecer aqui, nao derrubar o processo. */
        printf("STAGE3_EXCEPTION_TRACEBACK_INICIO\n");
        PyErr_Print();
        printf("STAGE3_EXCEPTION_TRACEBACK_FIM\n");
        return 0;
    }

    Py_DECREF(result);
    fprintf(stderr, "ERRO: trigger_controlled_exception deveria ter levantado ValueError\n");
    return -1;
}

int main(void) {
    Py_InitializeEx(0);
    if (!Py_IsInitialized()) {
        fprintf(stderr, "ERRO: Py_Initialize falhou\n");
        return 1;
    }

    double distance = 0.0;
    if (run_compute_distance(&distance) != 0) {
        fprintf(stderr, "ERRO: run_compute_distance falhou\n");
        Py_Finalize();
        return 1;
    }
    printf("STAGE3_DISTANCE_OK valor=%f\n", distance);

    if (run_controlled_exception() != 0) {
        fprintf(stderr, "ERRO: run_controlled_exception nao se comportou como esperado\n");
        Py_Finalize();
        return 1;
    }

    printf("STAGE3_OK\n");
    Py_Finalize();
    return 0;
}
