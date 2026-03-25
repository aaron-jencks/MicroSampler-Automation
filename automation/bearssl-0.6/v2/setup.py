from setuptools import setup, Extension

ext = Extension(
    "bearssl.v2",
    sources=[
        "python-module.c",
        "../../../apps/bearssl-0.6/src/codec/ccopy.c",
        "../../../apps/bearssl-0.6/src/int/i31_tmont.c",
        "../../../apps/bearssl-0.6/src/int/i31_montmul.c", 
        "../../../apps/bearssl-0.6/src/int/i31_modpow.c", 
        "../../../apps/bearssl-0.6/src/int/i31_ninv31.c", 
        "../../../apps/bearssl-0.6/src/int/i31_muladd.c", 
        "../../../apps/bearssl-0.6/src/util/util.c", 
        "../../../apps/bearssl-0.6/src/int/i31_sub.c", 
        "../../../apps/bearssl-0.6/src/int/i31_add.c", 
        "../../../apps/bearssl-0.6/src/int/i32_div32.c",
    ],
    include_dirs=[
        "../../../apps/bearssl-0.6/src",
        "../../../apps/bearssl-0.6/inc",
    ],
    extra_compile_args=[
        "-Os",
        "--static",
    ],
    define_macros=[
        ("LOCAL_X86_BUILD", "1"),
    ],
)

setup(
    name="bearssl",
    version="0.1",
    ext_modules=[ext],
)