from eea.eggmonkey.scm import get_scm
from mr.developer.extension import Extension
import cPickle
import os.path
import shutil


def learn(buildout):
    """Learn about the buildout
    
    We are interested in reading and caching the sources section of the buildout 
    """
    
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
        scm = get_scm(path, False)
        if scm.get_repo_url() != url:
            if not scm.is_dirty():
                print "EGGMONKEY: erasing %s as it has an outdated repo path"
                shutils.rmtree(path, ignore_errors=True)
