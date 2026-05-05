import ctypes
from ctypes import wintypes
import time
from PIL import ImageGrab

user32 = ctypes.windll.user32

# Find window by title substring
def enum_windows_callback(hwnd, lParam):
    length = user32.GetWindowTextLengthW(hwnd)
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    title = buff.value
    if 'maintenance_frontend' in title or '127.0.0.1:5175' in title:
        lParam.append(hwnd)
    return True

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.py_object)

hwnds = []
user32.EnumWindows(EnumWindowsProc(enum_windows_callback), hwnds)

if not hwnds:
    print("Could not find browser window.")
else:
    hwnd = hwnds[0]
    print(f"Found window: {hwnd}")
    
    # Restore window if minimized/maximized
    user32.ShowWindow(hwnd, 9) # SW_RESTORE
    time.sleep(0.5)
    
    # Bring to front
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    
    # Resize window to 800x1000 (x=0, y=0, width=800, height=1000)
    # SWP_NOZORDER = 0x0004
    user32.SetWindowPos(hwnd, 0, 0, 0, 800, 1000, 0x0004)
    time.sleep(1) # wait for render and transition
    
    # Capture screen
    # Get window rect
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    
    bbox = (rect.left, rect.top, rect.right, rect.bottom)
    print(f"Capturing bounding box: {bbox}")
    
    screenshot = ImageGrab.grab(bbox)
    screenshot.save('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/host_browser_telemetry.png')
    print("Saved host_browser_telemetry.png")
