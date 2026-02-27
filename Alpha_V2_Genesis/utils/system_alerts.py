import winsound
import ctypes
import threading
import time

def play_alert_sound(type="success"):
    """
    Plays a system sound based on type.
    Non-blocking (runs in thread).
    """
    def _play():
        if type == "success":
            # High-Low-High pattern
            winsound.Beep(1000, 200)
            winsound.Beep(1200, 200)
            winsound.Beep(1500, 300)
        elif type == "danger":
            # Low-Low rapid
            winsound.Beep(500, 200)
            winsound.Beep(500, 200)
        elif type == "neutral":
             winsound.Beep(800, 300)
             
    threading.Thread(target=_play).start()

def show_popup(title, message):
    """
    Shows a topmost message box.
    Non-blocking (runs in thread).
    """
    def _show():
        # MB_TOPMOST = 0x40000
        # MB_ICONINFORMATION = 0x40
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40000 | 0x40)
        
    threading.Thread(target=_show).start()

if __name__ == "__main__":
    play_alert_sound("success")
    show_popup("Alpha Architect", "Test Alert: System Functional")
