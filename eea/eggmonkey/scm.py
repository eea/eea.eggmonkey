from eea.eggmonkey.utils import EXTERNAL
from itertools import chain
import os
import re
import subprocess


ignore_patterns = [".*dist$", ".*egg-info$"]


class GenericSCM(object):
    """Base SCM class
    """

    def __init__(self, path, no_net):
        self.path = path
        self.no_net = no_net

    def execute(self, *args, **kwds):
        print EXTERNAL + " ".join(list(chain(*args)))
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
        self.execute(['svn', 'commit'] + paths + ['-m', message])

    def is_dirty(self):
        ret = subprocess.Popen(['svn', 'status', '.'],
                               stdout=subprocess.PIPE, cwd=self.path)
        out, err = ret.communicate()

        if ret.returncode == 0:
            flag = False
            for l in out.splitlines():
                matches = 0
                for r in ignore_patterns:
                    if re.search(r, l):
                        matches += 1
                if matches == 0:
                    flag = True

            return flag

        raise ValueError("Error when trying to get scm status: %s" % self.path)

    def get_repo_url(self):
        """
        """
        ret = subprocess.Popen(['svn', 'info'],
                               stdout=subprocess.PIPE, cwd=self.path)
        out, err = ret.communicate()

        if ret.returncode == 0:
            lines = out.splitlines()
            for line in lines:
                if line.startswith("URL:"):
                    url = line.split("URL:")[1].strip()
                    return url

        raise ValueError("Error when trying to get repo url: %s" % self.path)


class GitSCM(GenericSCM):
    """Implementation of git scm
    """

    def _get_modified(self):
        ret = subprocess.Popen(['git', 'status', '.'],
                               stdout=subprocess.PIPE, cwd=self.path)
        out, err = ret.communicate()
        if ret.returncode == 0:
            lines = out.splitlines()
        else:
            raise ValueError("Error when trying to get scm status: %s" %
                             self.path)

        modified = []
        for l in lines:
            if l.startswith("#") and l[1:].strip().startswith("modified:"):
                # should use find() to find first space char
                modified.append(l[1:].strip().split()[1])

        return modified

    def add_and_commit(self, paths, message=None):
        self.add(paths)
        message = message or "Added %s" % " ".join(paths)
        self.commit(paths, message)

    def add(self, paths):
        self.execute(["git", "add"] + paths)

    def commit(self, paths, message):
        if not paths:
            paths = self._get_modified()

        self.execute(['git', 'add'] + paths)
        self.execute(['git', 'commit', '-am', message])
        self.execute(['git', 'push'])

    def update(self, paths):
        self.execute(["git", "pull"])       # , "-u"

    def is_dirty(self):
        ret = subprocess.Popen(['git', 'status', '--porcelain',
                                '--untracked-files=no', '.'],
                               stdout=subprocess.PIPE,
                               cwd=self.path)
        out, err = ret.communicate()

        if ret.returncode == 0:
            return bool(out.splitlines())

        raise ValueError("Error when trying to get scm status: %s" % self.path)

    def get_repo_url(self):
        """
        """
        ret = subprocess.Popen(['git', 'config', '--get', 'remote.origin.url'],
                               stdout=subprocess.PIPE, cwd=self.path)
        out, err = ret.communicate()

        if ret.returncode == 0:
            return out.strip()

        raise ValueError("Error when trying to get repo url: %s" % self.path)


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
        self.execute(['hg', 'commit'] + paths + ['-m', message])
        self.execute(['hg', 'push'])

    def update(self, paths):
        self.execute(["hg", "pull", "-u"])

    def is_dirty(self):
        ret = subprocess.Popen(['hg', 'status', '-mar', '.'],
                               stdout=subprocess.PIPE, cwd=self.path)
        out, err = ret.communicate()

        if ret.returncode == 0:
            return bool(out.splitlines())

        raise ValueError("Error when trying to get scm status: %s" % self.path)

    def get_repo_url(self):
        """
        """
        ret = subprocess.Popen(['hg', 'paths', 'default'],
                               stdout=subprocess.PIPE, cwd=self.path)
        out, err = ret.communicate()

        if ret.returncode == 0:
            return out.strip()

        raise ValueError("Error when trying to get repo url: %s" % self.path)


def get_scm(path, no_net):
    files = os.listdir(path)
    scms = {
            'svn': ('.svn', SubversionSCM),
            'git': ('.git', GitSCM),
            'hg': ('.hg', MercurialSCM)
            }

    _scm = None
    for k, v in scms.items():
        marker, factory = v
        if marker in files:
            _scm = factory(path, no_net)
            break

    if _scm is None:
        raise ValueError("Could not determine scm type", path)

    return _scm
