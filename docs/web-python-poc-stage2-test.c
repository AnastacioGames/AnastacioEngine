/* Etapa 2 da PoC (docs/web-python-poc-plan.md): prova mínima de que
 * Py_Initialize() funciona em wasm32-emscripten e que um valor calculado
 * em Python volta corretamente para o C, com relato explícito de erro
 * se a inicialização falhar. Servir via `python3 -m http.server`
 * (Node sozinho não fecha esta etapa - ver plano). */

#include <Python.h>
#include <stdio.h>

static int run_python_and_get_value(long *out_value) {
    PyObject *main_module, *main_dict, *result;

    main_module = PyImport_AddModule("__main__");
    if (main_module == NULL) {
        PyErr_Print();
        return -1;
    }
    main_dict = PyModule_GetDict(main_module);

    result = PyRun_String(
        "def stage2_compute():\n"
        "    return 6 * 7\n"
        "stage2_result = stage2_compute()\n",
        Py_file_input, main_dict, main_dict);

    if (result == NULL) {
        PyErr_Print();
        return -1;
    }
    Py_DECREF(result);

    PyObject *value_obj = PyDict_GetItemString(main_dict, "stage2_result");
    if (value_obj == NULL) {
        fprintf(stderr, "stage2_result nao encontrado no namespace Python\n");
        return -1;
    }

    *out_value = PyLong_AsLong(value_obj);
    if (PyErr_Occurred()) {
        PyErr_Print();
        return -1;
    }
    return 0;
}

int main(void) {
    Py_InitializeEx(0);
    if (!Py_IsInitialized()) {
        fprintf(stderr, "ERRO: Py_Initialize falhou\n");
        return 1;
    }

    long value = 0;
    int rc = run_python_and_get_value(&value);

    if (rc != 0) {
        fprintf(stderr, "ERRO: execucao do script Python falhou\n");
        Py_Finalize();
        return 1;
    }

    printf("STAGE2_OK valor_recebido_do_python=%ld\n", value);

    Py_Finalize();
    return 0;
}
