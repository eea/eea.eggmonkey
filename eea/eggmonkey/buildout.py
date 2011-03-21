from mr.developer.extension import Extension
import cPickle
import os.path

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

