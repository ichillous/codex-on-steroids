"""Own validation descendants independently of the original parent's lifetime.

Windows children start suspended, enter a kill-on-close Job Object, and only
then execute. No externally supplied process ID is accepted. POSIX commands
start a new session whose process group remains owned after its leader exits.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time


class _WindowsJob:
    def __init__(self):
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        api = self.api
        api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        api.CreateJobObjectW.restype = wintypes.HANDLE
        api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                               ctypes.c_void_p, wintypes.DWORD]
        api.SetInformationJobObject.restype = wintypes.BOOL
        api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        api.AssignProcessToJobObject.restype = wintypes.BOOL
        api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        api.TerminateJobObject.restype = wintypes.BOOL
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
        api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        api.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenThread.restype = wintypes.HANDLE
        api.ResumeThread.argtypes = [wintypes.HANDLE]
        api.ResumeThread.restype = wintypes.DWORD

        class BasicLimits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                        ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimits),
                        ("IoInfo", IOCounters), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        class ThreadEntry(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                        ("th32ThreadID", wintypes.DWORD),
                        ("th32OwnerProcessID", wintypes.DWORD),
                        ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                        ("dwFlags", wintypes.DWORD)]

        self.ThreadEntry = ThreadEntry
        for name in ("Thread32First", "Thread32Next"):
            method = getattr(api, name)
            method.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
            method.restype = wintypes.BOOL
        self.handle = api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if not api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign_and_resume(self, process: subprocess.Popen) -> None:
        ctypes, api = self.ctypes, self.api
        # CPython owns this process handle. It refers to the suspended child
        # created here, avoiding a PID lookup or a parent-exit assignment race.
        if not api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        snapshot = api.CreateToolhelp32Snapshot(0x4, 0)  # SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        resumed = False
        try:
            entry = self.ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            present = api.Thread32First(snapshot, ctypes.byref(entry))
            while present:
                if entry.th32OwnerProcessID == process.pid:
                    thread = api.OpenThread(0x2, False, entry.th32ThreadID)  # SUSPEND_RESUME
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        previous = api.ResumeThread(thread)
                        if previous == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                        if previous != 1:
                            raise OSError("Validation thread did not have the expected suspend count")
                        resumed = True
                    finally:
                        api.CloseHandle(thread)
                entry.dwSize = ctypes.sizeof(entry)
                present = api.Thread32Next(snapshot, ctypes.byref(entry))
        finally:
            api.CloseHandle(snapshot)
        if not resumed:
            raise OSError("Could not locate the suspended validation thread")

    def stop(self) -> None:
        if self.handle and not self.api.TerminateJobObject(self.handle, 1):
            raise self.ctypes.WinError(self.ctypes.get_last_error())

    def close(self) -> None:
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.api.CloseHandle(handle):
                raise self.ctypes.WinError(self.ctypes.get_last_error())


class OwnedProcessTree:
    """A single spawned command and its descendants, with fail-closed startup."""

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.job = _WindowsJob() if os.name == "nt" else None
        self.closed = False

    def start(self, argv, **kwargs) -> subprocess.Popen:
        if self.process is not None or self.closed:
            raise RuntimeError("A process-tree owner can start only once")
        if self.job is not None:
            kwargs["creationflags"] = (subprocess.CREATE_NEW_PROCESS_GROUP
                                       | subprocess.CREATE_NO_WINDOW | 0x4)  # SUSPENDED
        else:
            kwargs["start_new_session"] = True
        try:
            self.process = subprocess.Popen(argv, **kwargs)
            if self.job is not None:
                self.job.assign_and_resume(self.process)
            return self.process
        except BaseException:
            # Assignment can fail before the suspended child enters the job.
            # Kill that owned process as well as closing the job; never resume.
            if self.process is not None and self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=10)
            self.close()
            raise

    def stop(self) -> None:
        if self.closed:
            return
        process = self.process
        if self.job is not None:
            self.job.stop()
        elif process is not None:
            # A exited leader does not imply its process group has ended.
            try:
                os.killpg(process.pid, signal.SIGTERM)
                time.sleep(0.1)
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process is not None:
            process.wait(timeout=10)

    def close(self) -> None:
        if self.closed:
            return
        try:
            if self.job is not None:
                self.job.close()  # Ends descendants even if the parent exited.
                if self.process is not None:
                    self.process.wait(timeout=10)
            else:
                self.stop()
        finally:
            self.closed = True
