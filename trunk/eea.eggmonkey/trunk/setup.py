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
            read('README.txt',),
            read('docs', 'HISTORY.txt'),
            ]),
        classifiers=[
            "Framework :: Buildout",
            "Programming Language :: Python",
            ],
        keywords='buildout',
        author='Tiberiu Ichim',
        author_email='tiberiu@eaudeweb.ro',
        url='https://svn.eionet.europa.eu/repositories/Zope/trunk/eea.eggmonkey',
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
