import comtypes
from comtypes import GUID, COMMETHOD, HRESULT, IUnknown
import ctypes

# Simple test to see if comtypes can load IMMDeviceEnumerator
try:
    from ctypes import POINTER, c_float
    from ctypes.wintypes import DWORD, BOOL
    print("Testing audio monitor...")
except Exception as e:
    print("Error:", e)
