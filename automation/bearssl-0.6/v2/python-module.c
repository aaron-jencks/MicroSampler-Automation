#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdio.h>
#include <stdlib.h>
#include "inner.h"
#include "utils.h"

static PyObject* keywdarg_v2(PyObject* self, PyObject* args, PyObject* kwargs) {
    int ok;
    size_t iters = 100;
    const char* key;
    static char* kwlist[] = {"iters", NULL};
    ok = PyArg_ParseTupleAndKeywords(
        args, kwargs, 
        "s|l", kwlist,
        &key, &iters
    );
    if(!ok) return NULL;

    unsigned char keyval[128];
    size_t blen;
    uint32_t x1[35] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35};
    uint32_t m1[35] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35};
    uint32_t tmp1[35], tmp2[35], r[35];

    str2hex(key, keyval, 128);
    blen = (iters + 7) >> 3;

    br_i31_modpow_v2(x1, r, keyval, blen, m1, br_i31_ninv31(m1[1]), tmp1, tmp2);

    printf(" done.\n");
    fflush(stdout);

    Py_RETURN_NONE;
}

static PyMethodDef keywdarg_methods[] = {
    {"v2", (PyCFunction)(void(*)(void))keywdarg_v2, METH_VARARGS | METH_KEYWORDS, "Run the v2 testcase."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef keywdarg_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "v2",
    .m_size = 0,
    .m_methods = keywdarg_methods,
};

PyMODINIT_FUNC
PyInit_v2(void)
{
    return PyModuleDef_Init(&keywdarg_module);
}