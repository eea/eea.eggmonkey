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
            read('docs', 'README.txt'),
            read('docs', 'HISTORY.txt'),
            ]),
        classifiers=[
            "Framework :: buildout",
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
            ],
        entry_points={
            "console_scripts":[
                "monkey = eea.eggmonkey.monkey:main" ,
                "print_unreleased_packages = eea.eggmonkey.monkey:print_unreleased_packages" ,
                ],
            "zc.buildout.unloadextension":[
                "monkey = eea.eggmonkey.buildout:learn",
                ]
            }
        )
