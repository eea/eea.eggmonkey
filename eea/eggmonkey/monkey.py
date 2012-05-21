#from StringIO import StringIO

from eea.eggmonkey.scm import get_scm
from eea.eggmonkey.utils import Error, EGGMONKEY, EXTERNAL, find_file, which
from eea.eggmonkey.history import FileHistoryParser, bump_history
from eea.eggmonkey.version import change_version, bump_version, get_version
import ConfigParser
import argparse
import cPickle
import os
import subprocess
import sys


def print_msg(*msgs):
    if isinstance(msgs, (list, tuple)):
        s = " ".join([str(m) for m in msgs])
    else:
        s = msgs
    print EGGMONKEY + s


def get_buildout():
    cwd        = os.getcwd()
    cache_file = open(os.path.join(cwd, '_eggmonkey.cache'), 'r')
    buildout   = cPickle.load(cache_file)
    cache_file.close()
    return buildout


class Monkey():
    """A package release monkey"""

    #used during releasing process
    tag_build = None
    tag_svn_revision = None


    _instructions = """
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
    """ #this needs to be updated everytime steps are modified

    def __init__(self, package, sources, args, config):
        self.package = package

        self.python = get_config(config, "python", args.python, section=package)
        self.domain = get_config(config, "domain", args.domain, section=package)
        self.manual_upload = get_config(config, "manual_upload", 
                                        args.manual_upload, section=package)
        self.mkrelease = get_config(config, "mkrelease", args.mkrelease, 
                                        section=package)

        self.no_net = args.no_network

        self.package_path = package_path = sources[package]['path']
        self.pkg_scm = get_scm(package_path, self.no_net)

        self.build_path = os.getcwd()
        self.build_scm = get_scm(self.build_path, self.no_net)

        self.instructions = filter(None, map(lambda s:s.strip(), 
                                    self._instructions.splitlines()))

    def check_package_sanity(self):
        #if self.pkg_scm.is_dirty():
            #raise Error("Package is dirty. Quiting")

        # check if we have hardcoded version in setup.py
        # this is a dumb but hopefully effective method: we look for a line
        # starting with version= and fail if there's a number on it
        setup_py = find_file(self.package_path, 'setup.py')
        f = open(setup_py)
        version = [l for l in f.readlines() if l.strip().startswith('version')]
        for l in version:
            for c in l:
                if c.isdigit():
                    raise Error("There's a hardcoded version in the "
                                "setup.py file. Quiting.")

        if not os.path.exists(self.package_path):
            raise Error("Path %s is invalid, quiting." % self.package_path)

        vv = get_version(self.package_path)
        vh = FileHistoryParser(self.package_path).get_current_version()

        if not "-dev" in vv:
            raise Error("Version.txt file is not at -dev. Quiting.")

        if not "-dev" in vh:
            raise Error("HISTORY.txt file is not at -dev. Quiting.")

        if vh != vv:
            raise Error("Latest version in HISTORY.txt is not the "
                        "same as in version.txt. Quiting.")

        # We depend on collective.dist installed in the python.
        # Installing eggmonkey under buildout with a different python doesn't
        # install properly the collective.dist

        print_msg("Installing collective.dist in ", self.python)
        cmd = self.python + " setup.py easy_install -q -U collective.dist"
        try:
            subprocess.check_call(cmd, cwd=self.package_path, shell=True)
        except subprocess.CalledProcessError:
            raise Error("Failed to install collective.dist in", self.python)

        # check if package metadata is properly filled
        try:
            cmd = self.python + " setup.py check --strict"
            subprocess.check_call(cmd, cwd=self.package_path, shell=True)
        except subprocess.CalledProcessError:
            raise Error("Package has improperly filled metadata. Quiting")

    def do_step(self, func, step, description, ignore_error=False):
        try:
            func()
        except Exception, e:
            if not ignore_error:
                print_msg("Got an error on step %s, but we continue: <%s>" % 
                            (step, e))
                print description
                return

    def release(self):
        self.check_package_sanity()

        for (n, description) in \
                map(lambda x:(x[0]+1, x[1]), enumerate(self.instructions)):
            step = getattr(self, 'step_%s' % n)
            step(n, description)

    def step_1(self, step, description):
        self.do_step(lambda:bump_version(self.package_path), step, description)

    def step_2(self, step, description):
        self.do_step(lambda:bump_history(self.package_path), step, description)

    def step_3(self, step, description):
        manifest_path = os.path.join(self.package_path, 'MANIFEST.in')
        if not os.path.exists(manifest_path):
            f = open(manifest_path, 'w+')

            f.write("global-exclude *pyc\nglobal-exclude *~\n" +
                    "global-exclude *.un~")
            f.close()
            self.pkg_scm.add_and_commit(self.package_path, ['MANIFEST.in'])

        if self.manual_upload:
            # when doing manual upload, if there's a setup.cfg file, 
            # we might get strange version so we change it here and 
            # again after the package release
            if 'setup.cfg' in os.listdir(self.package_path):
                print_msg("Changing setup.cfg to fit manual upload")
                f = open(os.path.join(self.package_path, 'setup.cfg'), 'rw+')
                b = []
                for l in f.readlines():
                    l = l.strip()
                    if l.startswith("tag_build"):
                        self.tag_build = l
                        b.append("tag_build = ")
                    elif l.startswith("tag_svn_revision"):
                        self.tag_svn_revision = l
                        b.append("tag_svn_revision = false")
                    else:
                        b.append(l)
                f.seek(0); f.truncate(0)
                f.write("\n".join(b))
                f.close()

    def step_4(self, step, description):
        domains = []
        for d in self.domain:
            domains.extend(['-d', d])
        cmd = [self.mkrelease, "-q"] + domains

        if not self.no_net:
            print EXTERNAL + " ".join(cmd)
            self.do_step(lambda:subprocess.check_call(cmd, cwd=self.package_path),
                    step, description, ignore_error=self.manual_upload)
        else:
            print_msg("Fake operation: ", " ".join(cmd))

        if self.manual_upload:
            for domain in self.domain:
                cmd = self.python + \
                        ' setup.py -q sdist --formats zip upload -r ' + domain
                if not self.no_net:
                    print EXTERNAL + cmd
                    self.do_step(
                        lambda:subprocess.check_call(cmd, cwd=self.package_path, 
                                                     shell=True), 
                        step, description)
                else:
                    print EGGMONKEY + "Fake operation: " + cmd

            if self.tag_build:   #we write the initial version of the setup.cfg file
                print_msg("Changing setup.cfg back to the original")
                f = open(os.path.join(self.package_path, 'setup.cfg'), 'rw+')
                b = []
                for l in f.readlines():
                    l = l.strip()
                    if l.startswith("tag_build"):
                        b.append(self.tag_build)
                    elif l.startswith("tag_svn_revision"):
                        b.append(self.tag_svn_revision)
                    else:
                        b.append(l)
                f.seek(0); f.truncate(0)
                f.write("\n".join(b))
                f.close()

    def step_5(self, step, description):
        self.do_step(lambda:self.build_scm.update(['versions.cfg']), 
                     step, description)

    def step_6(self, step, description):
        version = get_version(self.package_path)
        version_path = os.path.join(self.build_path, 'versions.cfg')
        self.do_step(lambda:change_version(path=version_path,
                               package=self.package, version=version), 
                     step, description)

    def step_7(self, step, description):
        version = get_version(self.package_path)
        self.do_step(lambda:self.build_scm.commit(paths=["versions.cfg"], 
             message='Updated %s to %s' % (self.package, version)), 
             step, description)

    def step_8(self, step, description):
        self.do_step(lambda:bump_version(self.package_path), step, description)

    def step_9(self, step, description):
        self.do_step(lambda:bump_history(self.package_path), step, description)

    def step_10(self, step, description):
        version = get_version(self.package_path)
        self.do_step(
            lambda:self.pkg_scm.commit([],
                                       message='Updated version for %s to %s' % 
                                               (self.package, version)), 
            step, description)


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
        #we need to redirect stderr to a file, I see no cleaner 
        #way to achieve this
        if (manual_upload != None) and manual_upload:
            err = open('_test_setuptools', 'wr+')
            cmd = [python, '-m', 'setuptools']
            exit_code = subprocess.call(cmd, stderr=err, stdout=err)
            err.seek(0)
            output = err.read()

            if "setuptools is a package and cannot be directly executed" \
                    not in output:
                raise Error("The specified Python doesn't have setuptools")

        #we don't support manual upload with multiple repositories
        if (manual_upload != None) and manual_upload and len(domain) > 1:
            raise Error("Can't have multiple repositories when doing a "
                        "manual upload")

    tocheck = [('default', {
        'domain':args.domain,
        'manual_upload':args.manual_upload,
        'mkrelease':args.mkrelease,
        'python':args.python,
    })]

    if config != None:
        for section in filter(lambda s:s.strip() != "*", config.sections()):
            tocheck.append((section, {
                'domain':get_config(config, "domain", "", 
                                    section=section).split() or [],
                'manual_upload':(get_config(config, "manual_upload", 
                                None, 'getboolean', section) in (False, True)) 
                                or args.manual_upload,
                'mkrelease':get_config(config, "mkrelease", None, 
                                    section=section) or args.mkrelease,
                'python':get_config(config, "python", None, 
                                    section=section) or args.python,
                }))

    for s in tocheck:
        _check(**s[1])


def get_config(cfg, name, value, method="get", section="*"):
    """Return a default value from a ConfigParser object

    @param cfg: ConfigParser object or None
    @param method: the method that will be used to get the default)
    @param value: the default value that will be returned, in case the 
                  option does not exist
    """
    if cfg is None:
        return value

    m = getattr(cfg, method)
    try:
        v = m(section, name)
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        v = value
    except ValueError:
        print_msg("Got an error parsing config file, option: %s and "
                  "section: %s" % (name, section))
        sys.exit(1)
    return v


def main(*a, **kw):
    try:
        sources, autocheckout = get_buildout()
    except Exception, e:
        print_msg("Got exception while trying to open monkey cache file: " + 
                  str(e))
        print "You need to run buildout first, before running the monkey"
        print "Also, make sure you run the eggmonkey from the buildout folder"
        sys.exit(1)

    config = None
    cfg_file = os.path.expanduser("~/.eggmonkey")
    if os.path.exists(cfg_file):
        config = ConfigParser.SafeConfigParser()
        config.read([cfg_file])

    cmd = argparse.ArgumentParser(
            u"Eggmonkey: easy build and release of eggs\n")

    cmd.add_argument('-n', "--no-network",
            action='store_const', const=True, default=False,
            help=u"Don't run network operations")

    cmd.add_argument('-u', "--manual-upload", action='store_const', 
            const=True, default=get_config(config, "manual_upload", 
                                            False, 'getboolean'),
            help=u"Manually upload package to eggrepo. Runs an extra " +
                 u"upload step to ensure package is uploaded on eggrepo.")

    cmd.add_argument('-a', "--autocheckout", action='store_const', const=True, 
            default=False, help=u"Process all eggs in autocheckout")

    cmd.add_argument("packages", nargs="*", metavar="PACKAGE",
                help=u"The packages to release. Can be any of: [ %s ]" %
                     u" ".join(sorted(sources.keys())))

    cmd.add_argument('-m', "--mkrelease",
                default=os.path.expanduser(get_config(config, "mkrelease", 
                                                              "mkrelease")),
                help=u"Path to mkrelease script. Defaults to 'mkrelease'")

    cmd.add_argument('-p', "--python",
                     default=os.path.expanduser(get_config(config, 
                                                        "python", "python")),
                     help=u"Path to Python binary which will be used "
                          u"to generate and upload the egg. "
                          u"Only used when doing --manual-upload")

    cmd.add_argument('-d', "--domain", action="append", 
                    help=u"The repository aliases. Defaults to 'eea'. "
                        u"Specify multiple times to upload egg "
                        u"to multiple repositories.",
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
            raise Error("ERROR: specify PACKAGES or autocheckout, "
                        "but not both")

        if args.autocheckout:
            packages = autocheckout

        check_global_sanity(args, config)

        for package in packages:
            if os.path.sep in package:
                raise Error("ERROR: you need to specify a package name, "
                            "not a path")
            if package not in sources:
                raise Error("ERROR: Package %s can't be found. Quiting." 
                                 % package)

            print_msg("Releasing package: ", package)
            monkey = Monkey(package, sources, args, config)
            monkey.release()

    except Error, e:
        print_msg(" ".join(e.args))
        sys.exit(1)

    sys.exit(0)

