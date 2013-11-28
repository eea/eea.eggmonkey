from colorama import Fore, Back, Style, init
import argparse
import cPickle
import datetime
import os
import subprocess
import sys


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

init()
EGGMONKEY = Fore.RED + "EGGMONKEY: " + Fore.RESET
EXTERNAL = Fore.BLUE + "RUNNING: " + Fore.RESET

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
    try:
        validate_version(version)
    except ValueError:
        print EGGMONKEY + "Got invalid version " + version
        sys.exit(1)

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
    try:
        validate_version(version)
    except ValueError:
        print EGGMONKEY + "Got invalid version " + version
        sys.exit(1)
    return version


class HistoryParser(object):
    header = None
    entries = None

    def __init__(self, path):
        self.header = []
        self.entries = []
        h_path = find_file(path, "HISTORY.txt")
        self.h_path = h_path
        f = open(h_path, 'r')
        content = f.read()
        self.original = content.splitlines()
        section_start = None
        section_end = None

        for nr, line in enumerate(self.original):

            if line and line[0].isdigit():
                if (nr == len(self.original) - 1):  #we test if it's the last line
                    section_start = nr  
                elif self.original[nr+1].strip()[0] in "-=~^":      #we test if next line is underlined
                    section_start = nr

            if (not line.strip()) and section_start:    #empty line, end of section
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
        try:
            validate_version(version)
        except ValueError:
            print EGGMONKEY + "Got invalid version " + version
            sys.exit(1)
        newver = _increment_version(version)
        today = str(datetime.datetime.now().date())
        section[0] = u"%s - (%s)" % (newver, today)
        section[1] = u"-" * len(section[0])

    def _create_dev_section(self):
        section = self.entries[0]
        header = section[0]
        version = header.split(" ")[0]
        try:
            validate_version(version)
        except ValueError:
            print EGGMONKEY + "Got invalid version " + version
            sys.exit(1)
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

    def get_current_version(self):
        """Return the last version"""
        section = self.entries[0]
        header = section[0]
        version = header.split(" ")[0].strip()
        try:
            validate_version(version)
        except ValueError:
            print EGGMONKEY + "Got invalid version " + version
            sys.exit(1)
        return version

def bump_history(path):
    hp = HistoryParser(path)
    hp.bump_version()


def validate_version(version):
    """See if what we consider a version number is actually a valid version number"""
    version = version.strip()

    if not "." in version:
        raise ValueError
    
    #all parts need to contain digits, only the last part can contain -dev
    parts = version.split('.')
    if not len(parts) > 1:
        raise ValueError

    for part in parts[:-1]:
        for c in part:
            if not c.isdigit():
                raise ValueError

    lp = parts[-1]
    if lp.endswith("-dev"):
        lp = lp.split("-dev")
        if (len(lp) != 2) and (lp[1] == ''):
            raise ValueError
        lp = lp[0]

    for c in lp:
        if not c.isdigit():
            raise ValueError

    return True


def change_version(path, package, version):
    f = open(path, 'rw+')
    b = []
    _l = "%s = %s\n" % (package, version)

    found = False
    for line in f.readlines():
        p = line.split("=")[0].strip()
        if p == package:
            b.append(_l)
            found = True
        else:
            b.append(line)

    if not found:
        b.append(_l)

    f.truncate(0); f.seek(0)
    f.write("".join(b))
    f.close()


def do_step(func, step, ignore_error=False):
    try:
        func()
    except Exception, e:
        if not ignore_error:
            print EGGMONKEY + "Got an error on step %s, but we continue: <%s>" % (step, e)
            return
            
            #while True:
                #ans = raw_input(EGGMONKEY + "Do you want to continue? (y/n/q) ")
                #if ans.lower() in "ynq":
                    #break

            #if ans.lower() == "y":
                #return

            #print "Carry on with the manual steps described in the instructions below"
            #print "-" * 40
            #print INSTRUCTIONS

            #sys.exit(1)


def release_package(package, sources, args):
    package_path = sources[package]['path']
    check_package_sanity(package_path)
    no_net = args.no_network

    do_step(lambda:bump_version(package_path), 1)
    do_step(lambda:bump_history(package_path), 2)

    tag_build = None
    tag_svn_revision = None

    if args.manual_upload:
        #when doing manual upload, if there's a setup.cfg file, we might get strange version
        #so we change it here and again after the package release
        if 'setup.cfg' in os.listdir(package_path):
            print EGGMONKEY + "Changing setup.cfg to fit manual upload"
            f = open(os.path.join(package_path, 'setup.cfg'), 'rw+')
            b = []
            for l in f.readlines():
                l = l.strip()
                if l.startswith("tag_build"):
                    tag_build = l
                    b.append("tag_build = ")
                elif l.startswith("tag_svn_revision"):
                    tag_svn_revision = l
                    b.append("tag_svn_revision = false")
                else:
                    b.append(l)
            f.seek(0); f.truncate(0)
            f.write("\n".join(b))
            f.close()

    cmd = [args.mkrelease, '-d', args.domain]
    if not no_net:
        print EXTERNAL + " ".join(cmd)
        do_step(lambda:subprocess.check_call(cmd, cwd=package_path), 
                3, ignore_error=args.manual_upload)
    else:
        print EGGMONKEY + "Fake operation: ", " ".join(cmd)

    if args.manual_upload:
        cmd = 'python setup.py sdist upload -r ' + args.domain
        if not no_net:
            print EXTERNAL + cmd
            do_step(lambda:subprocess.check_call(cmd, cwd=package_path, shell=True), 4)
        else:
            print EGGMONKEY + "Fake operation: ", cmd

        if tag_build:   #we write the initial version of the setup.cfg file
            print EGGMONKEY + "Changing setup.cfg back to the original"
            f = open(os.path.join(package_path, 'setup.cfg'), 'rw+')
            b = []
            for l in f.readlines():
                l = l.strip()
                if l.startswith("tag_build"):
                    b.append(tag_build)
                elif l.startswith("tag_svn_revision"):
                    b.append(tag_svn_revision)
                else:
                    b.append(l)
            f.seek(0); f.truncate(0)
            f.write("\n".join(b))
            f.close()

    cmd = ['svn', 'up', 'versions.cfg']
    print EXTERNAL + " ".join(cmd)
    do_step(lambda:subprocess.check_call(cmd, cwd=os.getcwd()), 5)

    version = get_version(package_path)
    do_step(lambda:change_version(path=os.path.join(os.getcwd(), 'versions.cfg'), 
                   package=package, version=version), 6)

    cmd = ['svn', 'ci', 'versions.cfg', '-m', 'Updated version for %s to %s' % (package, version)]
    print EXTERNAL + " ".join(cmd)
    if not no_net:
        do_step(lambda:subprocess.check_call(cmd, cwd=os.getcwd()), 7)
    else:
        print EGGMONKEY + "Fake operation: ", " ".join(cmd)

    do_step(lambda:bump_version(package_path), 8)
    do_step(lambda:bump_history(package_path), 9)

    version = get_version(package_path)
    cmd = ['svn', 'ci', '-m', 'Change version to %s' % version]
    print EXTERNAL + " ".join(cmd)
    if not no_net:
        do_step(lambda:subprocess.check_call(cmd, cwd=package_path), 10)
    else:
        print EGGMONKEY + "Fake operation: ", " ".join(cmd)

    return


def which(program):
    """Check if an executable exists"""
    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def check_global_sanity(args):

    #check if mkrelease can be found
    if not which(args.mkrelease):
        print EGGMONKEY + "Could not find mkrelease script. Quiting."
        sys.exit(1)

    if not os.path.exists("versions.cfg"):
        print EGGMONKEY + "versions.cfg file was not found. Quiting."
        sys.exit(1)


def check_package_sanity(package_path):
    if not os.path.exists(package_path):
        print EGGMONKEY + "Path %s is invalid, quiting." % package_path
        sys.exit(1)

    version = get_version(package_path)
    if not "-dev" in version:
        print EGGMONKEY + "Version.txt file is not at -dev. Quiting."
        sys.exit(1)

    history = HistoryParser(package_path)
    version = history.get_current_version()
    if not "-dev" in version:
        print EGGMONKEY + "HISTORY.txt file is not at -dev. Quiting."
        sys.exit(1)


def main(*a, **kw):
    try:
        sources, autocheckout = get_buildout()
    except Exception, e:
        print EGGMONKEY + "Got exception while trying to open monkey cache file: ", e
        print "You need to run buildout first, before running the monkey"
        print "Also, make sure you run the eggmonkey from the buildout folder"
        sys.exit(1)

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
                     u" ".join(sorted(sources.keys())))

    cmd.add_argument('-m', "--mkrelease", 
                help=u"Path to mkrelease script. Defaults to 'mkrelease'",
                default="mkrelease")

    cmd.add_argument('-d', "--domain", help=u"The repository alias. Defaults to 'eea'", default="eea")

    args = cmd.parse_args()

    packages = args.packages
    if not packages and not args.autocheckout:
        cmd.print_help()
        sys.exit(1)

    if packages and args.autocheckout:
        print EGGMONKEY + "ERROR: specify PACKAGES or autocheckout, but not both"
        sys.exit(1)

    if args.autocheckout:
        packages = autocheckout

    check_global_sanity(args)
    for package in packages:
        if '/' in package:
            print EGGMONKEY + "ERROR: you need to specify a package name, not a path"
        if package not in sources:
            print EGGMONKEY + "ERROR: Package %s can't be found. Quiting." % package
            sys.exit(1)

        print EGGMONKEY + "Releasing package: ", package
        release_package(package, sources, args)

    sys.exit(0)