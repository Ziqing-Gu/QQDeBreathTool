"""Optional native protection against extremely slow IIR subnormal tails."""
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
import ctypes
import os
import sys


@lru_cache(maxsize=1)
def _library():
    if sys.platform != 'win32':
        return None
    directory = os.environ.get('QQDEBREATH_NATIVE_DIR')
    path = (Path(directory) if directory else Path(__file__).parent) / 'qq_fp_control.dll'
    if not path.is_file():
        return None  # Source-only/non-Windows use retains the original arithmetic.
    lib = ctypes.CDLL(str(path))
    lib.qq_fp_get.argtypes = []
    lib.qq_fp_get.restype = ctypes.c_uint32
    lib.qq_fp_enter.argtypes = []
    lib.qq_fp_enter.restype = ctypes.c_uint32
    lib.qq_fp_restore.argtypes = [ctypes.c_uint32]
    lib.qq_fp_restore.restype = None
    return lib


@contextmanager
def suppress_denormals():
    lib = _library()
    previous = lib.qq_fp_enter() if lib is not None else None
    try:
        yield
    finally:
        if lib is not None:
            lib.qq_fp_restore(previous)
