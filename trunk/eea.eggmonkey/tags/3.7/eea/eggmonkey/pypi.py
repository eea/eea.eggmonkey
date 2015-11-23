#
# Check if EEA packages are released also on pypi and plone.org
#
import os
import sys
import json
from eventlet.green import urllib2
from eea.eggmonkey.history import HistoryParser
from eea.eggmonkey.utils import find_file


PYPI_PACKAGE = 'http://pypi.python.org/pypi/%s/json'
PYPI_RELEASE = 'http://pypi.python.org/pypi/%s/%s'
PLONE_PACKAGE = 'http://plone.org/products/%s'
PLONE_RELEASE = 'http://plone.org/products/%s/releases/%s'


def check_package_on_server(package, server):
    """ Check if package is released on given server
    """
    meta = {}
    try:
        conn = urllib2.urlopen(server % package)
    except urllib2.HTTPError:
        return meta
    else:
        if 'json' in server:
            try:
                meta = json.loads(conn.read())
            except Exception:
                meta = {}
        else:
            meta = {'info': {}}
        conn.close()
        return meta


def check_release_on_server(package, version, server):
    """ Check if package version is available on given server
    """
    try:
        conn = urllib2.urlopen(server % (package, version))
    except urllib2.HTTPError:
        return False
    else:
        conn.close()
        return True


def print_pypi_plone_unreleased_eggs(pypi=True, plone=False):
    """ Print packages that aren't released on pypi or plone.org
    """
    versions = {}
    vfile = 'versions.cfg'
    args = sys.argv
    if len(args) > 1:
        vfile = args[1]

    with open(vfile, 'r') as vfile:
        for line in vfile:
            line = line.strip().split('=')
            if len(line) == 2:
                package, version = [x.strip() for x in line]
                versions[package] = version

    errors = False
    for package, version in versions.items():
        if 'eea' not in package.lower():
            continue

        # Check plone.org
        if plone:
            if check_package_on_server(package, PLONE_PACKAGE):
                if not check_release_on_server(package, version, PLONE_RELEASE):
                    errors = True
                    print "%30s:  %10s  not on plone.org" % (package, version)

        # Check pypi
        if pypi:
            _pypi = check_package_on_server(package, PYPI_PACKAGE)
            if _pypi:
                serverVersion = _pypi.get('info', {}).get('version', 'None')
                if not serverVersion == version:
                    errors = True
                    print "%30s:  %10s  not on pypi.python.org  %10s" % (
                        package, version, serverVersion)

    if errors:
        sys.exit(1)

def print_pypi_not_on_plone():
    """ Print packages that are released on pypi but not on plone.org
    """
    versions = {}
    vfile = 'versions.cfg'
    args = sys.argv
    if len(args) > 1:
        vfile = args[1]

    with open(vfile, 'r') as vfile:
        for line in vfile:
            line = line.strip().split('=')
            if len(line) == 2:
                package, version = [x.strip() for x in line]
                versions[package] = version

    errors = False
    for package, version in versions.items():
        if 'eea' not in package.lower():
            continue

        if check_package_on_server(package, PYPI_PACKAGE):
            if not check_package_on_server(package, PLONE_PACKAGE):
                errors = True
                print "%30s:  not on plone.org" % package

    if errors:
        sys.exit(1)

def print_unreleased_packages():
    """Given a directory with packages (such as the src/ created by mr.developer,
    traverses it and print packages that have changes in their history files
    that haven't been released as eggs
    """

    unreleased = []
    changes = ''

    args = sys.argv
    if len(args) == 1:
        print "You need to provide a path where to look for packages"
        sys.exit(1)

    folder = args[1]
    for name in os.listdir(folder):
        dirname = os.path.join(folder, name)
        if not os.path.isdir(dirname):
            continue

        print "Looking in package %s" % dirname
        try:
            history = find_file(dirname, "HISTORY.txt")
        except ValueError:
            print "Did not find a history file, skipping"
            continue
        lines = open(history).read()
        parser = HistoryParser(lines)
        try:
            if len(parser.entries[0]) > 2:
                if parser.entries[0][2].strip() != "*":    #might be just a placeholder star
                    unreleased.append(name)
                    changes += "\n\n%s\n============================\n" % dirname
                    for change in parser.entries[0][2:]:
                        changes += "\n" + change
        except:
            print "Got an error while processing history file, skipping"
            continue

    if not unreleased:
        print "No unreleased packages have been found"
    else:
        print "\n\n\n"
        print changes
        print "\n\n"
        print "The following packages have unreleased modifications:",
        print ", ".join(unreleased)

    sys.exit(0)

