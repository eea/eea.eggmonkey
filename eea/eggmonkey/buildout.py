from eea.eggmonkey.scm import get_scm
from mr.developer.extension import Extension
from yolk.pypi import CheeseShop, check_proxy_setting, ProxyTransport
import base64
import cPickle
import os.path
import shutil
import sys
import urllib2
import xmlrpclib

def learn(buildout):
    """ Learn about the buildout
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
    """ We want to erase folders in src for which the source path is out of date
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
        if url.endswith('/'):
            url = url[:-1]
        if scm.get_repo_url() != url:
            if not scm.is_dirty():
                print "EGGMONKEY: erasing %s as it has an outdated repo path" % pkg
                shutil.rmtree(path, ignore_errors=True)

class AuthTransport(ProxyTransport):
    """ Authenticated transport
    """

    def __init__(self, username, password):
        ProxyTransport.__init__(self)
        self._username = username
        self._password = password

    def request(self, host, handler, request_body, verbose):
        '''Send xml-rpc request using proxy'''
        #We get a traceback if we don't have this attribute:
        self.verbose = verbose
        url = 'http://' + host + handler
        request = urllib2.Request(url)
        request.add_data(request_body)
        # Note: 'Host' and 'Content-Length' are added automatically
        base64string = base64.encodestring('%s:%s' % 
                    (self._username, self._password)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string) 
        request.add_header('User-Agent', self.user_agent)
        request.add_header('Content-Type', 'text/xml')
        proxy_handler = urllib2.ProxyHandler()
        opener = urllib2.build_opener(proxy_handler)
        fhandle = opener.open(request)
        return(self.parse_response(fhandle))

class EEAEggRepo(CheeseShop):
    """ eea eggrepo
    """

    def get_xmlrpc_server(self):
        """
        Returns PyPI's XML-RPC server instance
        """
        check_proxy_setting()

        URL = "http://eggrepo.eea.europa.eu/"
        import getpass

        username = raw_input("Enter username for %s: " % URL)
        password = getpass.getpass("Enter password: ")

        try:
            return xmlrpclib.Server(URL, 
                                transport=AuthTransport(username, password), 
                                verbose=True)
        except IOError:
            self.logger("ERROR: Can't connect to XML-RPC server: %s" \
                    % XML_RPC_SERVER)

def check_latest():
    """
    Problems:

      * we use several third-party packages that are not included in a 
        normal plone release. We want to keep those up to date
      * we keep all packages pinned to avoid getting unstable releases 
        and we need to know when newer releases are available

    The tool should do the following:

      * watch the egg repos we are using (pypi, eea eggrepo) and report 
        when new versions of packages are available, especially for the 
        third-party packages
      * parse the buildout files (including on-the-web cfgs) and report 
        of conflicts between versions
      * this should be implemented as a buildout tool
      * this tool should be run in automatic by Jenkins and report when 
        new versions are available
    """

    with open('.picked_versions.cfg', 'r') as f:
        v = {}
        for l in f.readlines():
            if l.strip() and (l[0] not in "[#]"):
                name, version = l.split("=")
                v[name.strip()] = version.strip()

    skipped = []
    if os.path.exists('.skipped_packages'):
        with open(".skipped_packages") as f:
            skipped = [x.strip() for x in f.readlines() if x.strip()]

    picked_versions = v
    #repos = [EEAEggRepo(), CheeseShop(), ] #order is important
    repos = [CheeseShop(), ] #order is important
    flag = 0

    for name, v in picked_versions.items():
        if name in skipped:
            continue

        print "Checking new version for", name
        for pypi in repos:
            new_name, versions = pypi.query_versions_pypi(name)
            if versions:
                break

        if versions:
            latest = versions[0]
        else:
            print "Could not find any version for this package"
            continue
        if latest != v:
            print "Package %s - %s" % (name, v), " has a new version: ", latest
            flag = 1

    sys.exit(flag)

def check_version_files():
    pass
