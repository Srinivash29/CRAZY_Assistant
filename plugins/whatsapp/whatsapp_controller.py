import subprocess
import time
import psutil
import win32gui
import win32con
import win32process


WHATSAPP_APP_ID = (
    "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"
)


def open_whatsapp():
    """Launch WhatsApp Desktop on Windows."""
    try:
        subprocess.Popen(
            [
                "explorer.exe",
                f"shell:AppsFolder\\{WHATSAPP_APP_ID}",
            ],
            shell=False,
        )
        return True, "WhatsApp launch requested."

    except OSError as error:
        return False, f"Could not launch WhatsApp: {error}"


def find_whatsapp_window():
    """Find the main WhatsApp Desktop window."""
    matches = []

    def inspect_window(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd).strip()

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = psutil.Process(pid).name().lower()
        except (OSError, psutil.Error):
            return

        if process_name == "whatsapp.root.exe" and title:
            matches.append((hwnd, title))

    win32gui.EnumWindows(inspect_window, None)
    return matches


def focus_whatsapp():
    """Launch WhatsApp if needed, then try to focus its window."""
    windows = find_whatsapp_window()

    if not windows:
        open_whatsapp()
        time.sleep(3)
        windows = find_whatsapp_window()

    if not windows:
        return False, "WhatsApp window not found."

    hwnd, title = windows[0]

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        win32gui.SetForegroundWindow(hwnd)

        return True, f"Focus requested for: {title}"

    except Exception as error:
        return False, f"Could not focus WhatsApp: {error}"
