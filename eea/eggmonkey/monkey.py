#from StringIO import StringIO
from colorama import Fore, init # Back, Style
import ConfigParser
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


def print_msg(*msgs):
    if isinstance(msgs, (list, tuple)):
        s = " ".join([str(m) for m in msgs])
    else:
        s = msgs
    print EGGMONKEY + s

class Error(Exception):
    """ EggMonkey runtime error """


MANIFEST = """global-exclude *pyc
global-exclude *~
global-exclude *.un~
"""


def get_buildout():
    cwd        = os.getcwd()
    cache_file = open(os.path.join(cwd, '_eggmonkey.cache'), 'r')
    buildout   = cPickle.load(cache_file)
    cache_file.close()
    return buildout


def find_file(path, name):
    for root, _dirs, names in os.walk(path):
        if name in names:
            return os.path.join(root, name)

    raise ValueError("File not found: %s in %s" % (name, path))


def get_digits(s):
    """Returns only the digits in a string"""
    return "".join(filter(lambda c:c.isdigit(), s))


def _increment_version(version):
    devel  = version.endswith('dev') or version.endswith('svn')
    ver    = version.split('-')[0].split('.')
    ver    = map(get_digits, ver)
    minor  = int(ver[-1]) + int(not devel)
    newver = ".".join(ver[:-1]) + ".%s%s" % (minor, (not devel and "-dev" or ""))
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
        raise Error("Got invalid version " + version)

    newver = _increment_version(version)
    f.truncate(0); f.seek(0) 
    f.write(newver)
    f.close()


def get_version(path):
    """Retrieves the version for a package
    """
    v_path = find_file(path, "version.txt")
    f      = open(v_path, 'r')
    version = f.read().strip()
    try:
        validate_version(version)
    except ValueError:
        raise Error("Got invalid version " + version)

    return version


class HistoryParser(object):
    """A history parser that receives a list of lines in constructor"""

    header = None
    entries = None

    def __init__(self, original):
        self.header   = []
        self.entries  = []
        self.original = original.splitlines()
        section_start = None
        section_end   = None

        header_flag   = True
        for nr, line in enumerate(self.original):
            if line and (line[0].isdigit() or (line[0] == 'r' and line[1].isdigit())):
                if (nr == len(self.original) - 1):  #we test if it's the last line
                    section_start = nr  
                elif self.original[nr+1].strip()[0] in "-=~^":      #we test if next line is underlined
                    section_start = nr
                header_flag = False

                #we travel through the file until we find a new section start
                nl = nr + 1
                while nl < len(self.original):
                    if self.original[nl] and (self.original[nl][0].isdigit() or 
                            (self.original[nl][0] == 'r' and self.original[nl][1].isdigit())):
                        section_end = nl - 1
                        break
                    nl += 1

            if not section_start and header_flag:   #if there's no section, this means we have file header
                self.header.append(line)

            if section_start and section_end:   # a section is completed
                self.entries.append(filter(lambda li:li.strip(), #we filter empty lines
                                           self.original[section_start:section_end])) 
                section_start = None
                section_end = None

            if section_start and (not section_end) and (nr == len(self.original) - 1):  #end of file means end of section
                section_end = len(self.original)
                self.entries.append(filter(lambda li:li.strip(), #we filter empty lines
                                           self.original[section_start:section_end])) 

    def _create_released_section(self):
        section = self.entries[0]
        header  = section[0]
        version = header.split(" ")[0]
        try:
            validate_version(version)
        except ValueError:
            raise Error("Got invalid version " + version)

        newver     = _increment_version(version)
        today      = str(datetime.datetime.now().date())
        section[0] = u"%s - (%s)" % (newver, today)
        section[1] = u"-" * len(section[0])

    def _create_dev_section(self):
        section = self.entries[0]
        header  = section[0]
        version = header.split(" ")[0]
        try:
            validate_version(version)
        except ValueError:
            raise Error("Got invalid version " + version)

        newver = _increment_version(version)
        line   = u"%s - (unreleased)" % (newver)

        self.entries.insert(0, [
                line,
                u"-" * len(line)
            ])

    def get_current_version(self):
        """Return the last version"""
        section = self.entries[0]
        header  = section[0]
        version = header.split(" ")[0].strip()
        try:
            validate_version(version)
        except ValueError:
            raise Error("Got invalid version " + version)

        return version


class FileHistoryParser(HistoryParser):
    """A history parser that also does file operations"""

    def __init__(self, path):
        h_path      = find_file(path, "HISTORY.txt")
        self.h_path = h_path
        f           = open(h_path, 'r')
        content     = f.read()
        HistoryParser.__init__(self, content)
        f.close()

    def write(self):
        f = open(self.h_path, 'rw+')
        f.truncate(0); f.seek(0)
        f.write("\n".join([l for l in self.header if l.strip()]))
        f.write("\n\n")
        for section in self.entries:
            f.write("\n".join([line for line in section if line.strip()]))
            f.write("\n\n")
        f.close()

    def bump_version(self):
        section = self.entries[0]
        header  = section[0]

        is_dev  = u'unreleased' in header.lower()

        if is_dev:
            self._create_released_section()
        else:
            self._create_dev_section()

        self.write()


def bump_history(path):
    hp = FileHistoryParser(path)
    hp.bump_version()


def validate_version(version):
    """See if what we consider a version number is actually a valid version number"""
    version = version.strip()

    if not "." in version:
        raise ValueError

    if version.endswith("."):
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
            print_msg("Got an error on step %s, but we continue: <%s>" % (step, e))
            print INSTRUCTIONS
            return
            

def release_package(package, sources, args, config):
    python = get_config(config, "python", args.python, section=package)
    domain = get_config(config, "domain", args.domain, section=package)
    manual_upload = get_config(config, "manual_upload", args.manual_upload, section=package)
    mkrelease = get_config(config, "mkrelease", args.mkrelease, section=package)

    no_net = args.no_network

    package_path = sources[package]['path']
    check_package_sanity(package_path, python, mkrelease, no_net)

    do_step(lambda:bump_version(package_path), 1)
    do_step(lambda:bump_history(package_path), 2)

    tag_build = None
    tag_svn_revision = None

    manifest_path = os.path.join(package_path, 'MANIFEST.in')
    if not os.path.exists(manifest_path):
        f = open(manifest_path, 'w+')
        f.write(MANIFEST)
        f.close()
        cmd = ['svn', 'add', 'MANIFEST.in']
        subprocess.check_call(cmd, cwd=package_path)

    if manual_upload:
        #when doing manual upload, if there's a setup.cfg file, we might get strange version
        #so we change it here and again after the package release
        if 'setup.cfg' in os.listdir(package_path):
            print_msg("Changing setup.cfg to fit manual upload")
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

    domains = []
    for d in domain:
        domains.extend(['-d', d])
    cmd = [mkrelease, "-q"] + domains    #, '-d', args.domain]
    if not no_net:
        print EXTERNAL + " ".join(cmd)
        do_step(lambda:subprocess.check_call(cmd, cwd=package_path), 
                3, ignore_error=manual_upload)
    else:
        print_msg("Fake operation: ", " ".join(cmd))

    if manual_upload:
        cmd = python + ' setup.py -q sdist --formats zip upload -r ' + domain[0]
        if not no_net:
            print EXTERNAL + cmd
            do_step(lambda:subprocess.check_call(cmd, cwd=package_path, shell=True), 4)
        else:
            print EGGMONKEY + "Fake operation: " + cmd

        if tag_build:   #we write the initial version of the setup.cfg file
            print_msg("Changing setup.cfg back to the original")
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
    if not no_net:
        print EXTERNAL + " ".join(cmd)
        do_step(lambda:subprocess.check_call(cmd, cwd=os.getcwd()), 5)
    else:
        print_msg("Fake operation: ", " ".join(cmd))

    version = get_version(package_path)
    do_step(lambda:change_version(path=os.path.join(os.getcwd(), 'versions.cfg'), 
                   package=package, version=version), 6)

    cmd = ['svn', 'ci', 'versions.cfg', '-m', 'Updated version for %s to %s' % (package, version)]
    if not no_net:
        print EXTERNAL + " ".join(cmd)
        do_step(lambda:subprocess.check_call(cmd, cwd=os.getcwd()), 7)
    else:
        print_msg("Fake operation: ", " ".join(cmd))

    do_step(lambda:bump_version(package_path), 8)
    do_step(lambda:bump_history(package_path), 9)

    version = get_version(package_path)
    cmd = ['svn', 'ci', '-m', 'Change version for %s to %s' % (package, version)]
    if not no_net:
        print EXTERNAL + " ".join(cmd)
        do_step(lambda:subprocess.check_call(cmd, cwd=package_path), 10)
    else:
        print_msg("Fake operation: ", " ".join(cmd))

    return


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


def check_global_sanity(args, config):
    #we check sanity for the arguments that come from the command line
    #and also arguments that come for each package from the configuration file

    if not os.path.exists("versions.cfg"):
        raise Error("versions.cfg file was not found. Quiting.")

    def _check(domain, manual_upload, mkrelease, python):

        #check if mkrelease can be found
        if ((mkrelease, python) != (None, None)) and (mkrelease == python):
            raise Error("Wrong parameters for python or mkrelease. Quiting.")

        if (mkrelease != None) and not which(mkrelease):
            raise Error("Could not find mkrelease script. Quiting.")

        #we check if this python has setuptools installed
        #we need to redirect stderr to a file, I see no cleaner way to achieve this
        if (manual_upload != None) and manual_upload:
            err = open('_test_setuptools', 'wr+')
            cmd = [python, '-m', 'setuptools']
            exit_code = subprocess.call(cmd, stderr=err, stdout=err)
            err.seek(0)
            output = err.read()

            if "setuptools is a package and cannot be directly executed" not in output:
                raise Error("The specified Python doesn't have setuptools")

        #we don't support manual upload with multiple repositories
        if (manual_upload != None) and manual_upload and len(domain) > 1:
            raise Error("Can't have multiple repositories when doing a manual upload")

    tocheck = [('default', {
        'domain':args.domain,
        'manual_upload':args.manual_upload,
        'mkrelease':args.mkrelease,
        'python':args.python,
    })]

    if config != None:
        for section in filter(lambda s:s.strip() != "*", config.sections()):
            tocheck.append((section, {
                'domain':get_config(config, "domain", "", section=section).split() or [],
                'manual_upload':(get_config(config, "manual_upload", None, 'getboolean', section) in (False, True)) or args.manual_upload,
                'mkrelease':get_config(config, "mkrelease", None, section=section) or args.mkrelease,
                'python':get_config(config, "python", None, section=section) or args.python,
                }))

    for s in tocheck:
        _check(**s[1])


def check_package_sanity(package_path, python, mkrelease, no_net=False):

    try:
        cmd = ["svn", "up"]
        if not no_net:
            subprocess.check_call(cmd, cwd=package_path)
    except subprocess.CalledProcessError:
        raise Error("Package is dirty. Quiting")

    #check if we have hardcoded version in setup.py
    #this is a dumb but hopefully effective method: we look for a line 
    #starting with version= and fail if there's a number on it
    setup_py = find_file(package_path, 'setup.py')
    f = open(setup_py)
    version = [l for l in f.readlines() if l.strip().startswith('version')]
    for l in version:
        for c in l:
            if c.isdigit():
                raise Error("There's a hardcoded version in the setup.py file. Quiting.")

    if not os.path.exists(package_path):
        raise Error("Path %s is invalid, quiting." % package_path)

    vv = get_version(package_path)
    vh = FileHistoryParser(package_path).get_current_version()

    if not "-dev" in vv:
        raise Error("Version.txt file is not at -dev. Quiting.")

    if not "-dev" in vh:
        raise Error("HISTORY.txt file is not at -dev. Quiting.")

    if vh != vv:
        raise Error("Latest version in HISTORY.txt is not the same as in version.txt. Quiting.")

    #we depend on collective.dist installed in the python.
    #Installing eggmonkey under buildout with a different python doesn't
    #install properly the collective.dist
    print_msg("Installing collective.dist in ", python)
    cmd = python + " setup.py easy_install -q -U collective.dist"
    try:
        subprocess.check_call(cmd, cwd=package_path, shell=True)
    except subprocess.CalledProcessError:
        raise Error("Failed to install collective.dist in", python)

    #if not no_net:
        #try:
            #subprocess.check_call(cmd, cwd=package_path, shell=True)
        #except subprocess.CalledProcessError:
            #raise Error("Failed to install collective.dist in", python)
    #else:
        #print_msg("Fake operation: " + cmd)

    #check if package metadata is properly filled
    try:
        cmd = python + " setup.py check --strict"
        subprocess.check_call(cmd, cwd=package_path, shell=True)
    except subprocess.CalledProcessError:
        raise Error("Package has improperly filled metadata. Quiting")


def get_config(cfg, name, value, method="get", section="*"):
    """Return a default value from a ConfigParser object

    @param cfg: ConfigParser object or None
    @param method: the method that will be used to get the default)
    @param value: the default value that will be returned, in case the option does not exist
    """
    if cfg is None:
        return value

    m = getattr(cfg, method)
    try:
        v = m(section, name)
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        v = value
    except ValueError:
        print_msg("Got an error parsing config file, option: %s and section: %s" % (name, section))
        sys.exit(1)
    return v


def main(*a, **kw):
    try:
        sources, autocheckout = get_buildout()
    except Exception, e:
        print_msg("Got exception while trying to open monkey cache file: " + str(e))
        print "You need to run buildout first, before running the monkey"
        print "Also, make sure you run the eggmonkey from the buildout folder"
        sys.exit(1)

    config = None
    cfg_file = os.path.expanduser("~/.eggmonkey")
    if os.path.exists(cfg_file):
        config = ConfigParser.SafeConfigParser()
        config.read([cfg_file])

    cmd = argparse.ArgumentParser(u"Eggmonkey: easy build and release of eggs\n")

    cmd.add_argument('-n', "--no-network", 
            action='store_const', const=True, default=False,
            help=u"Don't run network operations")

    cmd.add_argument('-u', "--manual-upload", action='store_const', const=True, 
                default=get_config(config, "manual_upload", False, 'getboolean'),
                help=u"Manually upload package to eggrepo. Runs an extra " +
                     u"upload step to ensure package is uploaded on eggrepo.")

    cmd.add_argument('-a', "--autocheckout", action='store_const', const=True, default=False,
                     help=u"Process all eggs in autocheckout")

    cmd.add_argument("packages", nargs="*", metavar="PACKAGE", 
                help=u"The packages to release. Can be any of: [ %s ]" % 
                     u" ".join(sorted(sources.keys())))

    cmd.add_argument('-m', "--mkrelease", 
                default=os.path.expanduser(get_config(config, "mkrelease", "mkrelease")),
                help=u"Path to mkrelease script. Defaults to 'mkrelease'")

    cmd.add_argument('-p', "--python", 
                     default=os.path.expanduser(get_config(config, "python", "python")),
                     help=u"Path to Python binary which will be used to generate and upload the egg. "
                          u"Only used when doing --manual-upload")

    cmd.add_argument('-d', "--domain", action="append", help=u"The repository aliases. Defaults to 'eea'. "
                        "Specify multiple times to upload egg to multiple repositories.", 
                        default=get_config(config, "domain", "").split() or [],
                    )

    args = cmd.parse_args()

    if not args.domain:
        args.domain = ['eea']

    packages = args.packages
    if not packages and not args.autocheckout:
        cmd.print_help()
        sys.exit(1)

    if args.no_network:
        print_msg("Running in OFFLINE mode")

    try:
        if packages and args.autocheckout:
            raise Error("ERROR: specify PACKAGES or autocheckout, but not both")

        if args.autocheckout:
            packages = autocheckout

        check_global_sanity(args, config)

        for package in packages:
            if os.path.sep in package:
                raise Error("ERROR: you need to specify a package name, not a path")
            if package not in sources:
                raise Error("ERROR: Package %s can't be found. Quiting." % package)

            print_msg("Releasing package: ", package)
            release_package(package, sources, args, config)

    except Error, e:
        print_msg(" ".join(e.args))
        sys.exit(1)

    sys.exit(0)
