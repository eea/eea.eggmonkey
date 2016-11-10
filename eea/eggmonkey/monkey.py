from eea.eggmonkey.history import FileHistoryParser
from eea.eggmonkey.scm import get_scm
from eea.eggmonkey.utils import Error, EGGMONKEY, EXTERNAL, find_file, which
from eea.eggmonkey.version import change_version, bump_version, get_version
from itertools import chain
from packaging.version import Version
from zest.pocompile.compile import find_lc_messages
import ConfigParser
import argparse
import cPickle
import os
import subprocess
import sys


Failure = object()
Success = object()


def print_msg(*msgs):
    """Output a message with a special colored line prefix
    """
    if isinstance(msgs, (list, tuple)):
        s = " ".join([str(m) for m in msgs])
    else:
        s = msgs
    print EGGMONKEY + s


def get_buildout():
    cwd = os.getcwd()
    cache_file = open(os.path.join(cwd, '_eggmonkey.cache'), 'r')
    buildout = cPickle.load(cache_file)
    cache_file.close()
    return buildout


def bump_pkg(pkg_path, final=True):
    """Bump both version files (history+version.txt) for a package
    """

    hp = FileHistoryParser(pkg_path)
    hp.bump_version()
    bump_version(pkg_path)

    vh = hp.get_current_version()
    vv = get_version(pkg_path)

    def check_final(x, final):
        return (final and ('dev' not in x)) or ((not final) and ('dev' in x))

    def check_versions(x, y, final):
        return (x == y) and check_final(x, final)

    if not check_versions(vv, vh, final):
        f = final and 'final' or 'devel'
        print_msg("There is something wrong with package version when "
                  "trying to bump to ", f)
        print_msg("HISTORY.txt version is at", vh)
        print_msg("version.txt version is at", vv)
        sys.exit(1)


class Monkey():
    """A single package release utility.

    It does the jobs nobody else wants to do by hand."""

    # used during releasing process
    tag_build = None
    tag_svn_revision = None

    _instructions = """
    #1. Bump version.txt to correct version; from .dev0 to final. Update history file with release date; Record final release date
    #2. Prepare the package for release
    #3. Run "mkrelease -qp -d eea" in package dir; (Optional) Run "python setup.py sdist upload -r eea"
    #4. Update versions.cfg file in buildout: svn up eea-buildout/versions.cfg
    #5. Change version for package in eea-buildout/versions.cfg
    #6. Commit versions.cfg file: svn commit versions.cfg
    #7. Bump package version file; From final to +1-dev. Update history file. Add Unreleased section
    #8. SVN commit the dev version of the package.
    """ # this needs to be updated everytime steps are modified
    _dummy = """
    """

    def __init__(self, package, sources, args, config):
        self.package = package

        self.python = get_config(config,
                                 "python", args.python, section=package)

        self.domain = get_config(config,
                                 "domain", None, section=package) or ['eea']
        self.domain = args.domain or self.domain
        if isinstance(self.domain, basestring):
            self.domain = [self.domain]

        self.interactive = get_config(config, "interactive",
                                      args.interactive, section=package)
        self.verbose = get_config(config,
                                  "verbose", args.verbose, section=package)
        self.debug = get_config(config, "debug", args.debug, section=package)
        self.mkrelease = get_config(config, "mkrelease", args.mkrelease,
                                    section=package)

        self.no_net = args.no_network
        self.no_buildout_update = args.no_buildout_update

        self.package_path = package_path = sources[package]['path']
        self.pkg_scm = get_scm(package_path, self.no_net)

        self.build_path = os.getcwd()
        self.build_scm = get_scm(self.build_path, self.no_net)

        self.instructions = filter(None, map(lambda s: s.strip(),
                                             self._instructions.splitlines()))

    def check_package_sanity(self):
        # if self.pkg_scm.is_dirty():
            # raise Error("Package is dirty. Quiting")

        if not os.path.exists(self.package_path):
            raise Error("Path %s is invalid, quiting." % self.package_path)

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

        vv = get_version(self.package_path)
        vh = FileHistoryParser(self.package_path).get_current_version()

        vv_version = Version(vv)
        if not vv_version.is_prerelease:
            raise Error("Version.txt file does not contain a dev version. "
                        "Quiting.")

        vh_version = Version(vh)
        if not vh_version.is_prerelease:
            raise Error("HISTORY.txt file does not contain a dev version. "
                        "Quiting.")

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
            # raise Error("Failed to install collective.dist in", self.python)
            pass    # easier not to fail here

        # check if package metadata is properly filled
        try:
            cmd = self.python + " setup.py check --strict"
            subprocess.check_call(cmd, cwd=self.package_path, shell=True)
        except subprocess.CalledProcessError:
            print "Make sure that the package following metadata filled in:"
            print " - name"
            print " - version"
            print " - url"
            print " - author and author_email"
            print " - maintainer and maintainer_email"
            raise Error("Package has improperly filled metadata. Quiting")

    def do_step(self, func, step, description, interactive=False):
        """Execute in a callable in a controlled situation.

        If the callable fails due to an error, we interact with the user and
        prompt what the solution should be: raise the error or return Failure,
        which means that the callable has not succeded but we want to ignore
        that problem
        """

        a = 'r'

        while a == 'r':

            try:
                func()
                break
            except Exception, e:

                if not interactive:
                    print_msg('Got error "%s" on step %s and we abort' %
                              (e, step))
                    print_msg("We were doing: %s" % description)
                    raise

                print_msg('Got error "%s" on step %s' % (e, step))
                print_msg("We were doing: %s" % description)

                a = 'X'
                while a.lower() not in 'ari':
                    a = raw_input(
                        "[A]bort, [R]etry, [I]gnore? ").lower().strip()

                if a == 'i':
                    return Failure
                elif a == 'a':
                    print e
                    sys.exit(1)
                else:
                    a = 'r'

        return Success

    def release(self):
        self.check_package_sanity()

        for (n, description) in \
                map(lambda x: (x[0]+1, x[1]), enumerate(self.instructions)):
            step = getattr(self, 'step_%s' % n)
            step(n, description)
            if self.debug:
                print_msg("Debugging step", n, ": ", description)
                import pdb
                pdb.set_trace()

    def step_1(self, step, description):
        """Bump the version in the version.txt file
        """
        def bump():
            return bump_pkg(self.package_path, final=True)

        def commit():
            return self.pkg_scm.commit(message="Bump version and history file")

        def do():
            return bump() and commit()

        self.do_step(do, step, description, interactive=True)
        if self.verbose:
            vv = get_version(self.package_path)
            print_msg("Bumped version to ", vv)

    def step_2(self, step, description):
        """Fix the MANIFEST.in file, compile po files and fix setup.cfg file
        """
        # Fix the MANIFEST.in file
        manifest_path = os.path.join(self.package_path, 'MANIFEST.in')
        if not os.path.exists(manifest_path):
            f = open(manifest_path, 'w+')

            f.write("global-exclude *.pyc\nglobal-exclude *~\n" +
                    "global-exclude *.un~\nglobal-include *.mo")
            f.close()
            self.pkg_scm.add_and_commit(['MANIFEST.in'])
        else:
            with open(manifest_path, 'a+') as f:
                if 'global-include *.mo' not in f.read():
                    f.seek(0)
                    f.write("\nglobal-include *.mo\n")

        # compile po files
        find_lc_messages(self.package_path)

        # If there's a setup.cfg file, we might get strange version so
        # we change it here and again after the package release
        if 'setup.cfg' in os.listdir(self.package_path):
            print_msg("Changing setup.cfg so we won't release a revision egg")
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
            f.seek(0)
            f.truncate(0)
            f.write("\n".join(b))
            f.close()

            # TODO: commit here

    def step_3(self, step, description):
        cmd = list(chain(*([(self.mkrelease, "-qp")] +
                           [('-d', d) for d in self.domain])))

        status = None
        if not self.no_net:
            print EXTERNAL + " ".join(cmd)
            status = self.do_step(lambda: subprocess.check_call(
                cmd, cwd=self.package_path),
                step, description, interactive=True
            )
        else:
            print_msg("Fake operation: ", " ".join(cmd))

        if status is Failure:
            for domain in self.domain:
                cmd = self.python + \
                        ' setup.py -q sdist --formats zip upload -r ' + domain
                if not self.no_net:
                    print EXTERNAL + cmd
                    self.do_step(
                        lambda: subprocess.check_call(
                            cmd, cwd=self.package_path, shell=True),
                        step, description)
                else:
                    print EGGMONKEY + "Fake operation: " + cmd

            if self.tag_build:
                # we write the initial version of the setup.cfg file
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
                f.seek(0)
                f.truncate(0)
                f.write("\n".join(b))
                f.close()

    def step_4(self, step, description):
        if self.no_buildout_update:
            return
        self.do_step(lambda: self.build_scm.update(['versions.cfg']),
                     step, description)

    def step_5(self, step, description):
        if self.no_buildout_update:
            return
        version = get_version(self.package_path)
        version_path = os.path.join(self.build_path, 'versions.cfg')
        self.do_step(lambda: change_version(
            path=version_path, package=self.package, version=version),
            step, description)

    def step_6(self, step, description):
        if self.no_buildout_update:
            return
        version = get_version(self.package_path)
        self.do_step(
            lambda: self.build_scm.commit(
                paths=["versions.cfg"],
                message='Updated %s to %s' % (self.package, version)),
            step, description)

    def step_7(self, step, description):
        def bump():
            return bump_pkg(self.package_path, final=False)

        def commit():
            return self.pkg_scm.commit(message="Bump version and history file")

        def do():
            return bump() and commit()

        self.do_step(do, step, description, interactive=True)
        if self.verbose:
            vv = get_version(self.package_path)
            print_msg("Bumped version to ", vv)

    def step_8(self, step, description):
        version = get_version(self.package_path)
        self.do_step(
            lambda: self.pkg_scm.commit([],
                                        message='Updated version for %s to %s'
                                        % (self.package, version)),
            step, description)


def check_global_sanity(args, config):
    # we check sanity for the arguments that come from the command line
    # and also arguments that come for each package from the configuration file

    if not os.path.exists("versions.cfg") and not args.no_buildout_update:
        raise Error("versions.cfg file was not found. Quiting.")

    def _check(domain, mkrelease, python):

        # check if mkrelease can be found
        if ((mkrelease, python) != (None, None)) and (mkrelease == python):
            raise Error("Wrong parameters for python or mkrelease. Quiting.")

        if (mkrelease is not None) and not which(mkrelease):
            raise Error("Could not find mkrelease script. Quiting.")

        # we check if this python has setuptools installed
        # we need to redirect stderr to a file, I see no cleaner
        # way to achieve this
        err = open('_test_setuptools', 'wr+')
        cmd = [python, '-m', 'setuptools']
        subprocess.call(cmd, stderr=err, stdout=err)
        err.seek(0)
        output = err.read()

        if "is a package and cannot be directly executed" \
                not in output:
            raise Error("The specified Python doesn't have setuptools")

    tocheck = [('default', {
        'domain': args.domain,
        'mkrelease': args.mkrelease,
        'python': args.python,
    })]

    if config is not None:
        for section in filter(lambda s: s.strip() != "*", config.sections()):
            tocheck.append((section, {
                'domain': get_config(config, "domain", "",
                                     section=section).split() or [],
                'mkrelease': get_config(config, "mkrelease", None,
                                        section=section) or args.mkrelease,
                'python': get_config(config, "python", None,
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

    cmd.add_argument('-v', "--verbose",
                     action='store_const', const=True, default=False,
                     help=u"Verbose. Will display content of "
                          u"external commands output")

    cmd.add_argument('-n', "--no-network",
                     action='store_const', const=True, default=False,
                     help=u"Don't run network operations")

    cmd.add_argument('-B', "--no-buildout-update",
                     action='store_const', const=True, default=False,
                     help=u"Don't update/upload buildout versions.cfg")

    cmd.add_argument('-D', "--debug",
                     action='store_const', const=True, default=False,
                     help=u"Debug with an interactive prompt")

    cmd.add_argument(
        '-i', "--interactive", action='store_const',
        const=True, default=get_config(config, "interactive",
                                       True, 'getboolean'),
        help=u"Set interactivity level to interactive. When set, "
        u"the eggmonkey will ask for confirmation in case "
        u"there are errors."
    )
    cmd.add_argument(
        '-I', "--noninteractive", action='store_const',
        const=True, default=get_config(config, "interactive",
                                       False, 'getboolean'),
        help=u"Set interactivity level to non-interactive. "
    )

    cmd.add_argument(
        '-a', "--autocheckout", action='store_const', const=True,
        default=False, help=u"Process all eggs in autocheckout")

    cmd.add_argument(
        "packages", nargs="*", metavar="PACKAGE",
        help=u"The packages to release. Can be any of: [ %s ]" %
        u" ".join(sorted(sources.keys())))

    cmd.add_argument(
        '-m', "--mkrelease",
        default=os.path.expanduser(get_config(config, "mkrelease",
                                              "mkrelease")),
        help=u"Path to mkrelease script. Defaults to 'mkrelease'")

    cmd.add_argument(
        '-p', "--python",
        default=os.path.expanduser(get_config(config,
                                              "python", "python")),
        help=u"Path to Python binary which will be used "
        u"to generate and upload the egg. "
        u"Only used when doing --manual-upload")

    cmd.add_argument(
        '-d', "--domain", action="append",
        help=u"The repository aliases. Defaults to 'eea'. "
        u"Specify multiple times to upload egg "
        u"to multiple repositories.",
        default=[],
    )

    args = cmd.parse_args()

    packages = args.packages
    if not packages and not args.autocheckout:
        cmd.print_help()
        sys.exit(1)

    if args.no_network:
        print_msg("Running in OFFLINE mode")

    if args.no_buildout_update:
        print_msg("Releasing wihout versions.cfg update")

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


def devify(*a, **kw):
    """Make a package to be at -dev, no matter what
    """

    try:
        sources, autocheckout = get_buildout()
    except Exception, e:
        print_msg("Got exception while trying to open monkey cache file: " +
                  str(e))
        print "You need to run buildout first, before running the monkey"
        print "Also, make sure you run the eggmonkey from the buildout folder"
        sys.exit(1)

    cmd = argparse.ArgumentParser(
            u"Devivy: make a package to be -dev version\n")

    cmd.add_argument("packages", nargs="*", metavar="PACKAGE",
                     help=u"The packages to devify. Can be any of: [ %s ]" %
                     u" ".join(sorted(sources.keys())))

    args = cmd.parse_args()
    packages = args.packages

    if not packages:
        cmd.print_help()
        sys.exit(1)

    for package in packages:
        package_path = sources[package]['path']
        parser = FileHistoryParser(package_path)
        has_changed = parser._make_dev()
        version = parser.get_current_version()
        version_file = find_file(package_path, 'version.txt')
        with open(version_file, 'w') as f:
            f.write(version)

        if has_changed:
            print "Changed version to -dev for package", package
        else:
            print "Package", package, " already at -dev"
