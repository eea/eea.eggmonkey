import sys
import argparse #optparse is deprecated
import cPickle
import os
import datetime
import subprocess


INSTRUCTIONS = """
#1. Bump version.txt to correct version; from -dev to final
#2. Update history file with release date; Record final release date
#3. Run "mkrelease -d eea" in package dir
#4. (Optional) Run "python setup.py sdist upload -r eea"
#5. Update versions.cfg file in buildout: svn up eea-buildout/versions.cfg
#6. Change version for package in eea-buildout/versions.cfg
#7. Commit versions.cfg file: svn commit versions.cfg
#8. Bump package version file; From final to +1-dev
#9. Update history file. Add Unreleased section
#10. SVN commit the dev version of the package.
"""


def get_buildout():
    cwd = os.getcwd()
    cache_file = open(os.path.join(cwd, '_eggmonkey.cache'), 'r')
    buildout = cPickle.load(cache_file)
    cache_file.close()
    return buildout


def find_file(path, name):
    for root, dirs, names in os.walk(path):
        if name in names:
            return os.path.join(root, name)

    raise ValueError("Version file not found")


def _increment_version(version):
    ver = version.split('-')[0].split('.')

    #TODO: handle the case for 0.1dev or 0.1svn
    minor = int(ver[-1]) + int(not version.endswith("dev"))
    devel = not version.endswith('dev')

    newver = ".".join(ver[:-1]) + ".%s%s" % (minor, (devel and "-dev" or ""))
    return newver


def bump_version(path):
    """Writes new versions into version file

    It will always go from dev to final and from released to 
    increased dev number. Example:

    Called first time:
    1.6.28-dev  =>  1.6.28

    Called second time:
    1.6.28  =>  1.6.29-dev
    """
    v_path = find_file(path, "version.txt")
    f = open(v_path, 'rw+')
    version = f.read().strip()
    newver = _increment_version(version)
    f.truncate(0); f.seek(0) 
    f.write(newver)
    f.close()


def get_version(path):
    """Retrieves the version for a package
    """
    v_path = find_file(path, "version.txt")
    f = open(v_path, 'r')
    version = f.read().strip()
    return version


class HistoryParser(object):
    header = []
    entries = []

    def __init__(self, path):
        h_path = find_file(path, "HISTORY.txt")
        self.h_path = h_path
        f = open(h_path, 'r')
        content = f.read()
        self.original = content.splitlines()
        section_start = None
        section_end = None

        for nr, line in enumerate(self.original):

            if line and line[0].isdigit():
                #we test if next line is underlined
                if (nr == len(self.original) - 1):
                    section_start = nr  #last line
                elif self.original[nr+1].strip()[0] in "-=~^":  
                    section_start = nr

            if (not line.strip()) and section_start:
                section_end = nr

            if not section_start:
                self.header.append(line)

            if section_start and section_end:
                self.entries.append(self.original[section_start:section_end])
                section_start = None
                section_end = None

            if section_start and (not section_end) and (nr == len(self.original) - 1):
                section_end = len(self.original)
                self.entries.append(self.original[section_start:section_end])

        f.close()

    def bump_version(self):
        section = self.entries[0]
        header = section[0]

        is_dev = u'unreleased' in header.lower()

        if is_dev:
            self._create_released_section()
        else:
            self._create_dev_section()

        self.write()

    def _create_released_section(self):
        section = self.entries[0]
        header = section[0]
        version = header.split(" ")[0]
        newver = _increment_version(version)
        today = str(datetime.datetime.now().date())
        section[0] = u"%s - (%s)" % (newver, today)
        section[1] = u"-" * len(section[0])

    def _create_dev_section(self):
        section = self.entries[0]
        header = section[0]
        version = header.split(" ")[0]
        newver = _increment_version(version)
        line = u"%s - (unreleased)" % (newver)

        self.entries.insert(0, [
                line,
                u"-" * len(line)
            ])

    def write(self):
        f = open(self.h_path, 'rw+')
        f.truncate(0); f.seek(0)
        f.write("\n".join([l for l in self.header if l.strip()]))
        f.write("\n\n")
        for section in self.entries:
            f.write("\n".join([l for l in section if l.strip()]))
            f.write("\n\n")
        f.close()


def bump_history(path):
    hp = HistoryParser(path)
    hp.bump_version()


def change_version(path, package, version):
    f = open(path, 'rw+')
    b = []
    _l = "%s = %s" % (package, version)
    for line in f.readlines():
        if line.strip().split("=")[0] == package:
            b.append(_l)
            found = True
        else:
            b.append(line)

    if not found:
        b.append(_l)

    f.truncate(0); f.seek(0)
    f.write("\n".join(b))
    f.close()


def do_step(func, step, ignore_error=False):
    try:
        func()
    except Exception, e:
        if not ignore_error:
            print "Got an error: <%s> while doing step %s" % (e, step)
            print "Continue with manual steps based on instructions bellow"
            print "-" * 40
            print INSTRUCTIONS

            sys.exit(0)


def release_package(package, sources, args):
    package_path = sources[package]['path']
    no_net = args.no_network

    do_step(lambda:bump_version(package_path), 1)
    do_step(lambda:bump_history(package_path), 2)

    cmd = [args.mkrelease, '-d', args.domain]
    if not no_net:
        do_step(lambda:subprocess.check_call(cmd, cwd=package_path), 3, ignore_error=True)
    else:
        print "Fake operation: ", " ".join(cmd)

    if args.manual_upload:
        #cmd = ['python', 'setup.py', 'sdist upload', '-r', args.domain]
        cmd = 'python setup.py sdist upload -r ' + args.domain
        if not no_net:
            do_step(lambda:subprocess.check_call(cmd, cwd=package_path, shell=True), 4)
        else:
            print "Fake operation: ", " ".join(cmd)

    cmd = ['svn', 'up', 'versions.cfg']
    do_step(lambda:subprocess.check_call(cmd, cwd=os.getcwd()), 5)

    version = get_version(package_path)
    do_step(lambda:change_version(path=os.path.join(os.getcwd(), 'versions.cfg'), 
                   package=package, version=version), 6)

    cmd = ['svn', 'ci', 'versions.cfg', '-m', '"Updated version for %s"' % package]
    if not no_net:
        do_step(lambda:subprocess.check_call(cmd, cwd=os.getcwd()), 7)
    else:
        print "Fake operation: ", " ".join(cmd)

    do_step(lambda:bump_version(package_path), 8)
    do_step(lambda:bump_history(package_path), 9)

    cmd = ['svn', 'ci', '-m', '"Change version to devel"']
    if not no_net:
        do_step(lambda:subprocess.check_call(cmd, cwd=package_path), 10)
    else:
        print "Fake operation: ", " ".join(cmd)

    return


def main(*a, **kw):
    try:
        sources, autocheckout = get_buildout()
    except Exception, e:
        print "Got exception while trying to open monkey cache file: ", e
        print "You need to run buildout first, before running the monkey"
        sys.exit(0)

    cmd = argparse.ArgumentParser(u"Eggmonkey: easy build and release of eggs\n")

    cmd.add_argument('-n', "--no-network", 
            action='store_const', const=True, default=False,
            help=u"Don't run network operations")

    cmd.add_argument('-u', "--manual-upload", action='store_const', const=True, default=False,
                help=u"Manually upload package to eggrepo. Runs an extra " +
                     u"upload step to ensure package is uploaded on eggrepo.")

    cmd.add_argument('-a', "--autocheckout", action='store_const', const=True, default=False,
                     help=u"Process all eggs in autocheckout")

    cmd.add_argument("packages", nargs="*", metavar="PACKAGE", 
                help=u"The packages to release. Can be any of: { %s }" % 
                     u" ".join(sources.keys()))

    cmd.add_argument('-m', "--mkrelease", 
                help=u"Path to mkrelease script. Defaults to 'mkrelease'",
                default="mkrelease")

    cmd.add_argument('-d', "--domain", help=u"The repository alias. Defaults to 'eea'", default="eea")

    args = cmd.parse_args()

    packages = args.packages
    if not packages and not args.autocheckout:
        cmd.print_help()
        sys.exit(0)

    if packages and args.autocheckout:
        print "ERROR: specify PACKAGES or autocheckout, but not both"
        sys.exit(0)

    if args.autocheckout:
        packages = autocheckout

    for package in packages:
        if package not in sources:
            print "ERROR: Package %s can't be found. Quiting." % package
            sys.exit(0)

        print "Releasing package: ", package
        release_package(package, sources, args)

