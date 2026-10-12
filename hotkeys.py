"""Six-key Windows input service; unhandled key events are never retained."""
import ctypes
from ctypes import wintypes
import queue
import sys
import threading
import os


def windows_context():
    """Read this process/thread's identity and desktops, without inspecting apps."""
    context = {'pid': os.getpid(), 'parent_pid': os.getppid(),
               'pointer_bits': ctypes.sizeof(ctypes.c_void_p)*8}
    if sys.platform != 'win32':
        return context
    try:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        user = ctypes.WinDLL('user32', use_last_error=True)
        kernel.GetCurrentThreadId.restype = wintypes.DWORD
        context['thread_id'] = kernel.GetCurrentThreadId()
        kernel.ProcessIdToSessionId.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        session = wintypes.DWORD()
        if kernel.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)):
            context['session'] = session.value
        user.GetThreadDesktop.argtypes = [wintypes.DWORD]
        user.GetThreadDesktop.restype = wintypes.HANDLE
        user.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                  ctypes.c_void_p, wintypes.DWORD,
                                                  ctypes.POINTER(wintypes.DWORD)]
        def name(handle):
            buffer = ctypes.create_unicode_buffer(256)
            needed = wintypes.DWORD()
            return buffer.value if user.GetUserObjectInformationW(handle, 2, buffer,
                                  ctypes.sizeof(buffer), ctypes.byref(needed)) else None
        context['thread_desktop'] = name(user.GetThreadDesktop(context['thread_id']))
        user.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        user.OpenInputDesktop.restype = wintypes.HANDLE
        user.CloseDesktop.argtypes = [wintypes.HANDLE]
        desktop = user.OpenInputDesktop(0, False, 1)
        if desktop:
            try:
                context['input_desktop'] = name(desktop)
            finally:
                user.CloseDesktop(desktop)
        else:
            context['input_desktop_error'] = ctypes.get_last_error()
    except Exception as error:
        context['context_error'] = str(error)
    return context


class GlobalHotkeys:
    KEYS = {'Right': 0x27, 'Left': 0x25, 'Up': 0x26, 'Down': 0x28,
            'Delete': 0x2E}

    def __init__(self):
        self.events = queue.Queue()
        self.registered = frozenset()
        self.hooked = frozenset()
        self.errors = {}
        self.hook_error = None
        self.received = dict.fromkeys(self.KEYS, 0)
        self.hook_received = dict.fromkeys(self.KEYS, 0)
        self.ready = threading.Event()
        self.closed = threading.Event()
        self.stopping = threading.Event()
        self.thread_id = None
        self.user32 = None
        self.hook = None
        self._callback = None
        self._pressed = set()
        self.context = None
        self.thread = threading.Thread(target=self._run, daemon=True, name='Blackjack five-key input')
        self.thread.start()

    @property
    def handled_keys(self):
        return self.registered | self.hooked

    def diagnostics(self):
        return dict(registered=sorted(self.registered), filtered_keys=sorted(self.hooked),
                    context=self.context,
                    registration_errors=self.errors.copy(), filter_error=self.hook_error,
                    received=self.received.copy(), filtered_received=self.hook_received.copy(),
                    message_thread_alive=self.thread.is_alive())

    def _install_filter(self, kernel32, missing):
        # Native low-level callbacks must return pointer-sized LRESULT on 64-bit Windows.
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                                          wintypes.WPARAM, wintypes.LPARAM)
        self.user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.CallNextHookEx.restype = ctypes.c_ssize_t
        self.user32.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, wintypes.HINSTANCE, wintypes.DWORD]
        self.user32.SetWindowsHookExW.restype = wintypes.HANDLE
        self.user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        self.user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        mapping = {vk: name for name, vk in self.KEYS.items() if name in missing}

        @callback_type
        def callback(code, kind, address):
            if code < 0 or self.stopping.is_set():
                return self.user32.CallNextHookEx(None, code, kind, address)
            # Only the virtual-key field is read to filter; other keys are immediately
            # passed through, without collecting their scan codes, text or timing.
            vk = ctypes.cast(address, ctypes.POINTER(wintypes.DWORD)).contents.value
            key = mapping.get(vk)
            if key is None:
                return self.user32.CallNextHookEx(None, code, kind, address)
            if kind in (0x0100, 0x0104):
                if key not in self._pressed:
                    self._pressed.add(key)
                    self.hook_received[key] += 1
                    self.events.put(key)
                return 1  # Consume only the requested keys; foreground does not act too.
            if kind in (0x0101, 0x0105):
                self._pressed.discard(key)
                return 1
            return self.user32.CallNextHookEx(None, code, kind, address)

        self._callback = callback  # Keep the native callback alive until unhooked.
        self.hook = self.user32.SetWindowsHookExW(13, callback, kernel32.GetModuleHandleW(None), 0)
        if self.hook:
            self.hooked = frozenset(missing)
        else:
            self.hook_error = ctypes.get_last_error()

    def _run(self):
        identifiers = {}
        try:
            self.context = windows_context()
            if sys.platform != 'win32':
                self.errors = {key: 'Windows required' for key in self.KEYS}
                return
            self.user32 = ctypes.WinDLL('user32', use_last_error=True)
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD
            self.thread_id = kernel32.GetCurrentThreadId()
            self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            self.user32.RegisterHotKey.restype = wintypes.BOOL
            self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self.user32.UnregisterHotKey.restype = wintypes.BOOL
            self.user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
            self.user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            self.user32.GetMessageW.restype = ctypes.c_int
            self.user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            self.user32.PostThreadMessageW.restype = wintypes.BOOL
            message = wintypes.MSG()
            self.user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            for index, (key, vk) in enumerate(self.KEYS.items(), 0xB100):
                if self.user32.RegisterHotKey(None, index, 0x4000, vk):
                    identifiers[index] = key
                else:
                    self.errors[key] = ctypes.get_last_error()
            self.registered = frozenset(identifiers.values())
            missing = frozenset(self.KEYS).difference(self.registered)
            if missing:
                self._install_filter(kernel32, missing)
            self.ready.set()
            if self.stopping.is_set() or not self.handled_keys:
                return
            while True:
                result = self.user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    if result < 0:
                        self.errors['message_loop'] = ctypes.get_last_error()
                    break
                if message.message == 0x0312 and message.wParam in identifiers:
                    self.received[identifiers[message.wParam]] += 1
                    self.events.put(identifiers[message.wParam])
        except Exception as error:
            self.errors['service'] = str(error)
        finally:
            if self.user32:
                if self.hook:
                    self.user32.UnhookWindowsHookEx(self.hook)
                    self.hook = None
                for identifier in identifiers:
                    self.user32.UnregisterHotKey(None, identifier)
            self.registered = self.hooked = frozenset()
            self._pressed.clear()
            self.ready.set()
            self.closed.set()

    def close(self):
        self.stopping.set()
        if self.user32 and self.thread_id:
            self.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
        self.thread.join(timeout=0.5)
