from eea.eggmonkey.scm import get_scm
from mr.developer.extension import Extension
from yolk.pypi import CheeseShop
import cPickle
import os.path
import shutil
import sys


def learn(buildout):
    """Learn about the buildout
    
    We are interested in reading and caching the sources section of the buildout 
    """
    
    import zc.buildout.easy_install as ez
    picked_versions = ez.Installer.__picked_versions

    with open(".picked_versions.cfg", "w") as f:
        f.write("[versions]\n")
        for k in sorted(picked_versions.keys()):
            f.write("%s = %s\n" % (k, picked_versions[k]))

    mrdeveloper = Extension(buildout)
    sources = mrdeveloper.get_sources()
    autocheckout = mrdeveloper.get_auto_checkout()

    directory = buildout['buildout']['directory']
    out = open(os.path.join(directory, '_eggmonkey.cache'), 'w')
    cPickle.dump([sources, autocheckout], out)
    out.close()


def cleanup_src(buildout):
    """We want to erase folders in src for which the source path is out of date
    """
    mrdeveloper = Extension(buildout)
    sources = mrdeveloper.get_sources()

    #sources is {'eea.eggmonkey': {'url': 
    #           'https://svn.eionet.europa.eu/repositories/Zope/trunk/eea.eggmonkey/trunk', 
    #           'path': '/home/tiberiu/eea.eggmonkey.testbuildout/src/eea.eggmonkey', 
    #           'kind': 'svn', 'name': 'eea.eggmonkey'}}

    for pkg, info in sources.items():
        path = info['path']
        url = info['url']
        if not os.path.exists(path):
            continue
        scm = get_scm(path, False)
        if scm.get_repo_url() != url:
            if not scm.is_dirty():
                print "EGGMONKEY: erasing %s as it has an outdated repo path" % pkg
                shutil.rmtree(path, ignore_errors=True)


def check_latest():
    """
    Problems:

        we use several third-party packages that are not included in a normal plone release. We want to keep those up to date
        we keep all packages pinned to avoid getting unstable releases and we need to know when newer releases are available

    The tool should do the following:

        watch the egg repos we are using (pypi, eea eggrepo) and report when new versions of packages are available, especially for the third-party packages
        parse the buildout files (including on-the-web cfgs) and report of conflicts between versions
        this should be implemented as a buildout tool
        this tool should be run in automatic by Jenkins and report when new versions are available
    """

    with open('.picked_versions.cfg', 'r') as f:
        v = {}
        for l in f.readlines():
            if l.strip() and (l[0] not in "[#]"):
                name, version = l.split("=")
                v[name.strip()] = version.strip()

    picked_versions = v
    pypi = CheeseShop()
    flag = 0
    for name, v in picked_versions.items():
        print "Checking new version for", name
        new_name, versions = pypi.query_versions_pypi(name)
        if versions:
            latest = versions[0]
        if latest != v:
            print "Package %s - %s" % (name, v), " has a new version: ", latest
            flag = 1
            
    sys.exit(flag)
