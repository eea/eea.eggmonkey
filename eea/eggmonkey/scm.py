from eea.eggmonkey.utils import EXTERNAL
from itertools import chain
import os
import subprocess


class GenericSCM(object):
    """Base SCM class
    """

    def __init__(self, path, no_net):
        self.path = path
        self.no_net = no_net

    def execute(self, *args, **kwds):
        print EXTERNAL + " ".join(list(chain(args)))
        if not self.no_net:
            subprocess.check_call(*args, cwd=self.path, **kwds)


class SubversionSCM(GenericSCM):
    """Implementation of subversion scm
    """

    def add_and_commit(self, paths, message=None):
        self.add(paths)
        message = message or "Added %s" % " ".join(paths)
        self.commit(paths, message)

    def add(self, paths):
        self.execute(["svn", "add"] + paths)

    def update(self, paths):
        self.execute(["svn", "update"] + paths)

    def commit(self, paths, message):
        self.execute(['svn', 'commmit'] + paths + ['-m', message])

    def is_dirty(self):
        ret = subprocess.Popen(['svn', 'status', '.'], 
                                stdout=subprocess.PIPE, cwd=self.path)
        out, err = ret.communicate()

        if ret.returncode == 0:
            return bool(out.splitlines())

        raise ValueError("Error when trying to get scm status")


class GitSCM(GenericSCM):
    """Implementation of git scm
    """

    def add_and_commit(self, paths, message=None):
        self.add(paths)
        message = message or "Added %s" % " ".join(paths)
        self.commit(paths, message)

    def add(self, paths):
        self.execute(["git", "add"] + paths)

    def commit(self, paths, message):
        self.execute(['git', 'commmit'] + paths + ['-m', message])
        self.execute(['git', 'push'])

    def update(self, paths):
        self.execute(["git", "pull", "-u"])

    def is_dirty(self):
        ret = subprocess.Popen(['git', 'status', '--porcelain', 
                '--untracked-files=no', '.'], stdout=subprocess.PIPE, 
                cwd=self.path)
        out, err = ret.communicate()

        if ret.returncode == 0:
            return bool(out.splitlines())

        raise ValueError("Error when trying to get scm status")


class MercurialSCM(GenericSCM):
    """Implementation of git scm
    """

    def add_and_commit(self, paths, message=None):
        self.add(paths)
        message = message or "Added %s" % " ".join(paths)
        self.commit(paths, message)

    def add(self, paths):
        self.execute(["hg", "add"] + paths)

    def commit(self, paths, message):
        self.execute(['hg', 'commmit'] + paths + ['-m', message])
        self.execute(['hg', 'push'])

    def update(self, paths):
        self.execute(["hg", "pull", "-u"])

    def is_dirty(self):
        ret = subprocess.Popen(['hg', 'status', '-mar', '.'], 
                                stdout=subprocess.PIPE, cwd=self.path)
        out, err = ret.communicate()

        if ret.returncode == 0:
            return bool(out.splitlines())

        raise ValueError("Error when trying to get scm status")


def get_scm(path, no_net):
    files = os.listdir(path)
    scms = {
            'svn':('.svn', SubversionSCM),
            'git':('.git', GitSCM),
            'hg':('.hg', MercurialSCM)
            }

    _scm = None
    for k, v in scms.items():
        marker, factory = v
        if marker in files:
            _scm = factory(path, no_net)
            break
    
    if _scm == None:
        raise ValueError ("Could not determine scm type")

    return _scm

