import win32process
import win32api
import win32con

pid = 12096
try:
    hproc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
    path = win32process.GetModuleFileNameEx(hproc, 0)
    print("Camfrog path:", path)
except Exception as e:
    print("Error:", e)
