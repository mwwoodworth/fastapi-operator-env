
from __future__ import annotations

import os
import sys

if __name__ == '__main__':
  # Ensure that the parent directory is not in sys.path.
  norm = lambda x: os.path.normpath(os.path.abspath(x))
  dirname = os.path.dirname(norm(__file__))
  sys.path[:] = [x for x in sys.path if norm(x) != dirname]
  del norm, dirname


import ctypes
import io
import json
import re
import shlex
import shutil
import subprocess
import tempfile
import traceback
import typing as t

if os.name == 'nt':
  import ctypes.wintypes as wintypes
  windll = ctypes.windll  # type: ignore
  WinError = ctypes.WinError  # type: ignore
  get_last_error = ctypes.get_last_error  # type: ignore
  class winapi:
    _WaitForSingleObject = windll.kernel32.WaitForSingleObject
    _WaitForSingleObject.restype = wintypes.DWORD
    _WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]

    @staticmethod
    def WaitForSingleObject(handle, ms=0):
      return winapi._WaitForSingleObject(handle, ms)

    _GetExitCodeProcess = windll.kernel32.GetExitCodeProcess
    _GetExitCodeProcess.restype = wintypes.BOOL
    _GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]

    @staticmethod
    def GetExitCodeProcess(handle):
      result = wintypes.DWORD()
      success = winapi._GetExitCodeProcess(handle, ctypes.byref(result))
      if not success:
        raise WinError(get_last_error())
      return result.value

    _MessageBox = windll.user32.MessageBoxW
    _MessageBox.restype = ctypes.c_int
    _MessageBox.argtypes = [wintypes.HWND, wintypes.LPWSTR, wintypes.LPWSTR, wintypes.UINT]

    @staticmethod
    def MessageBox(hwnd, text, caption, type):
      return winapi._MessageBox(hwnd, text, caption, type)

    class _SHELLEXECUTEINFO(ctypes.Structure):
      _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('fMask', wintypes.ULONG),
        ('hwnd', wintypes.HWND),
        ('lpVerb', wintypes.LPCSTR),
        ('lpFile', wintypes.LPCSTR),
        ('lpParameters', wintypes.LPCSTR),
        ('lpDirectory', wintypes.LPCSTR),
        ('nShow', ctypes.c_int),
        ('hInstApp', wintypes.HINSTANCE),
        ('lpIDList', wintypes.LPVOID),
        ('lpClass', wintypes.LPCSTR),
        ('hkeyClass', wintypes.HKEY),
        ('dwHotKey', wintypes.DWORD),
        ('DUMMYUNIONNAME', wintypes.HANDLE),
        ('hProcess', wintypes.HANDLE),
      ]

    _ShellExecuteEx = windll.shell32.ShellExecuteEx
    _ShellExecuteEx.restype = wintypes.BOOL
    _ShellExecuteEx.argtypes = [ctypes.POINTER(_SHELLEXECUTEINFO)]

    SW_HIDE = 0
    SW_MAXIMIMIZE = 3
    SW_MINIMIZE = 6
    SW_RESTORE = 9
    SW_SHOW = 5
    SW_SHOWDEFAULT = 10
    SW_SHOWMAXIMIZED = 3
    SW_SHOWMINIMIZED = 2
    SW_SHOWMINNOACTIVE = 7
    SW_SHOWNA = 8
    SW_SHOWNOACTIVE = 4
    SW_SHOWNORMAL = 1

    @staticmethod
    def ShellExecuteEx(hwnd=None, verb='', file='', parameters=None,
                       directory=None, show=SW_SHOW, mask=0):  # TODO: More parameters
      data = winapi._SHELLEXECUTEINFO()
      data.cbSize = ctypes.sizeof(data)
      data.fMask = mask
      data.hwnd = hwnd
      data.lpVerb = verb.encode()
      data.lpFile = file.encode()
      data.lpParameters = parameters.encode()
      data.lpDirectory = directory.encode()
      data.nShow = show
      data.hInstApp = None
      data.lpIDList = None
      data.lpClass = None
      data.hkeyClass = None
      data.dwHotKey = 0
      data.DUMMYUNIONNAME = None
      data.hProcess = None
      result = winapi._ShellExecuteEx(ctypes.byref(data))
      if not result:
        raise WinError(get_last_error())
      return {'hInstApp': data.hInstApp, 'hProcess': data.hProcess}


def alert(*msg: str) -> None:
  # TODO (@NiklasRosenstein): Support GUI alerts for other systems.
  message = ' '.join(map(str, msg))
  print(message, file=sys.stderr)
  sys.stderr.flush()
  if os.name == 'nt':
    winapi.MessageBox(None, message, "Python", 0)


def quote(s: str) -> str:
  if os.name == 'nt' and os.sep == '\\':
    s = s.replace('"', '\\"')
    if re.search(r'\s', s) or any(c in s for c in '<>'):
      s = '"' + s + '"'
  else:
    s = shlex.quote(s)
  return s


def is_root() -> bool:
  if os.name == 'nt':
    try:
      return bool(windll.shell32.IsUserAnAdmin())
    except:
      traceback.print_exc()
      print("ctypes.windll.shell32.IsUserAnAdmin() failed -- "
            "assuming not an admin.", file=sys.stderr)
      sys.stderr.flush()
      return False
  elif os.name == 'posix':
    return os.getuid() == 0
  else:
    raise RuntimeError('Unsupported os: {!r}'.format(os.name))


def elevate(command: str | list[str], cwd: str | None = None, environ: t.Mapping[str, str] | None  = None) -> None:
  """
  Runs a command as an admin in the specified *cwd* and *environ*. On Windows, this creates a temporary directory where
  this information is stored temporarily so that the new process can launch the proper subprocess.
  """

  if isinstance(command, str):
    command = shlex.split(command)

  if os.name == 'nt':
    return _elevate_windows(command, cwd, environ)

  elif os.name == 'posix':
    command = ['sudo', '-E'] + list(command)
    sys.exit(subprocess.call(command))

  else:
    raise RuntimeError('Unsupported os: {!r}'.format(os.name))


def _elevate_windows(command, cwd, environ):
  assert os.name == 'nt'
  datadir = tempfile.mkdtemp()
  try:
    # TODO: Maybe we could also use named pipes and transfer them
    #       via the processdata.json to the elevated process.
    # This file will receive all the process information.
    datafile = os.path.join(datadir, 'processdata.json')
    data = {
      'command': command,
      'cwd': cwd or os.getcwd(),
      'environ': environ or os.environ.copy(),
      'outfile': os.path.join(datadir, 'out.bin')
    }
    with open(datafile, 'w') as fp:
      json.dump(data, fp)

    # Ensure the output file exists.
    open(data['outfile'], 'w').close()

    # Create the windows elevated process that calls this file. This
    # file will then know what to do with the information from the
    # process data directory.
    hProc = winapi.ShellExecuteEx(
      file=sys.executable,
      verb='runas',
      parameters=' '.join(map(quote, [os.path.abspath(__file__), '--windows-process-data', datadir])),
      directory=datadir,
      mask=64,
      show=winapi.SW_HIDE
      )['hProcess']

    # Read the output from the process and write it to our stdout.
    with open(data['outfile'], 'rb+', 0) as outfile:
      while True:
        hr = winapi.WaitForSingleObject(hProc, 40)
        while True:
          line = outfile.readline()
          if not line: break
          sys.stdout.buffer.write(line)
        if hr != 0x102: break

    return winapi.GetExitCodeProcess(hProc)

  finally:
    try:
      shutil.rmtree(datadir)
    except:
      print("ERROR: Unable to remove data directory of elevated process.")
      print("ERROR: Directory at \"{}\"".format(datadir))
      traceback.print_exc()


def _elevate_windows_elevated(datadir):
  assert os.name == 'nt'
  datafile = os.path.join(datadir, 'processdata.json')
  with open(datafile, 'r') as pdata_fp:
    data = json.load(pdata_fp)

  try:
    with open(data['outfile'], 'wb', 0) as fp:
      sys.stderr = sys.stdout = io.TextIOWrapper(fp)
      os.environ.update(data['environ'])
      return subprocess.call(data['command'], cwd=data['cwd'], stdout=fp, stderr=fp)
  except:
    alert(traceback.format_exc())
    sys.exit(1)


def main(argv=None, prog=None):
  import argparse
  parser = argparse.ArgumentParser(prog=prog)
  parser.add_argument('--windows-process-data',
    help='The path to a Windows process data directory. This is used to '
      'provide data for the elevated process since no environment variables '
      'can be via ShellExecuteEx().')
  args, unknown = parser.parse_known_args(argv)

  if args.windows_process_data:
    if not is_root():
      alert("--windows-process-data can only be used in an elevated process.")
      sys.exit(1)
    sys.exit(_elevate_windows_elevated(args.windows_process_data))
  elif unknown:
    elevate(unknown)
    sys.exit()
  else:
    parser.print_usage()


_entry_point = lambda: sys.exit(main())

if __name__ == '__main__':
  _entry_point()
