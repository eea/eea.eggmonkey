import os
from os.path import join
from setuptools import setup, find_packages

def read(*pathnames):
    return open(os.path.join(os.path.dirname(__file__), *pathnames)).read()

name = 'eea.eggmonkey'
path = name.split('.') + ['version.txt']
version = open(join(*path)).read().strip()

setup(name=name,
        version=version,
        description="Automate releasing eggs with jarn.mkrelease",
        long_description='\n'.join([
            read('README.rst',),
            read('docs', 'HISTORY.txt'),
            ]),
        # http://pypi.python.org/pypi?%3Aaction=list_classifiers      
        classifiers=[
            "Framework :: Buildout",
            "Framework :: Zope2",
            "Framework :: Plone",
            "Framework :: Plone :: 4.0",
            "Framework :: Plone :: 4.1",
            "Framework :: Plone :: 4.2",
            "Framework :: Plone :: 4.3",
            "Programming Language :: Zope",
            "Programming Language :: Python",
            "Programming Language :: Python :: 2.7",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "License :: OSI Approved :: GNU General Public License (GPL)",
        ],

        keywords='EEA Add-ons Plone Zope buildout',
        author='European Environment Agency: IDM2 A-Team',
        author_email='eea-edw-a-team-alerts@googlegroups.com',
        url='https://github.com/eea/eea.eggmonkey',
        license='GPL',
        packages=find_packages(),
        namespace_packages=['eea'],
        include_package_data=True,
        zip_safe=False,
        test_suite = name + ".tests.test_suite",

        install_requires=[
            'setuptools',
            'mr.developer',
            'argparse', #TODO: test python version, it comes included with Python 2.7
            'colorama',
            'collective.dist',
            'jarn.mkrelease',
            'zest.pocompile',
            'yolk',
            'packaging',
            'eventlet',

            #anyvc and its required support for repositories
            #'anyvc',
            #'mercurial',
            #'subvertpy',
            #'dulwich',

            ],
        extras_require={
          'yum': [
              'apr-util-devel',
              'subversion-devel',
              ],
          'apt': [
              'libsvn-dev',
              'libaprutil1-dev'
          ]
        },
        entry_points={
            "console_scripts":[
                "monkey = eea.eggmonkey.monkey:main" ,
                "devify = eea.eggmonkey.monkey:devify" ,
                "check_latest = eea.eggmonkey.buildout:check_latest" ,
                "check_version_files = eea.eggmonkey.buildout:check_version_files" ,
                "print_unreleased_packages = eea.eggmonkey.pypi:print_unreleased_packages" ,
                "print_pypi_plone_unreleased_eggs = eea.eggmonkey.pypi:print_pypi_plone_unreleased_eggs",
                "print_pypi_not_on_plone = eea.eggmonkey.pypi:print_pypi_not_on_plone",
                #"testpypi = eea.eggmonkey.simplepypi:main",
                ],
            "zc.buildout.extension":[
                "cleanup_src = eea.eggmonkey.buildout:cleanup_src",
                ],
            "zc.buildout.unloadextension":[
                "monkey = eea.eggmonkey.buildout:learn",
                ]
            }
        )
