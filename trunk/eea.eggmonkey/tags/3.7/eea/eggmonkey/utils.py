from colorama import Fore, init as init_colorama
import os

EGGMONKEY = Fore.RED + "EGGMONKEY: " + Fore.RESET
EXTERNAL = Fore.BLUE + "RUNNING: " + Fore.RESET

init_colorama()


class Error(Exception):
    """ EggMonkey runtime error """


def find_file(path, name):
    for root, _dirs, names in os.walk(path):
        if name in names:
            return os.path.join(root, name)

    raise ValueError("File not found: %s in %s" % (name, path))


def which(program):
    """Check if an executable exists"""

    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    fpath, _fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None
