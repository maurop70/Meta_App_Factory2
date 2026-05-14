import win32gui
import win32ui
import win32con
from PIL import Image

def screenshot_window(hwnd, filename):
    rect = win32gui.GetWindowRect(hwnd)
    x, y, w, h = rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
    if w <= 0 or h <= 0: return
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(saveBitMap)
    saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)
    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
    img.save(filename)
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

def winEnumHandler(hwnd, ctx):
    if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
        title = win32gui.GetWindowText(hwnd)
        safe_title = ''.join([c for c in title if c.isalpha() or c.isdigit()]).rstrip()
        if safe_title:
            print(f'Capturing: {title}')
            try:
                screenshot_window(hwnd, f'c:/Dev/Antigravity_AI_Agents/Meta_App_Factory/window_{safe_title}.png')
            except Exception as e:
                pass

win32gui.EnumWindows(winEnumHandler, None)
