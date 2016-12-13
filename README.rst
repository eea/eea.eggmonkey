==============
EEA Egg Monkey
==============

This is an internal EEA tool to be used together with zc.buildout, mr.developer and
jarn.mkrelease. Its purpose is to automate a series of 10 steps that are
required in order to produce and upload an egg to an eggrepo.

The ten steps are:

1. Bump version.txt to correct version; from -dev to final
2. Update history file with release date; Record final release date
3. Run "mkrelease -d eea" in package dir
4. (Optional) Run "python setup.py sdist upload -r eea"
5. Update versions.cfg file in buildout: svn up eea-buildout/versions.cfg
6. Change version for package in eea-buildout/versions.cfg
7. Commit versions.cfg file: svn commit versions.cfg
8. Bump package version file; From final to +1-dev
9. Update history file. Add Unreleased section
10. SVN commit the dev version of the package.

Note: the eggmonkey is scm aware, so it will switch to using svn, git or hg
wherever appropriate, but only git and svn are the better tested scm options.

Requirements
============
eea.eggmonkey requires python2.6+

Instalation
===========
To use it, you need to add eea.eggmonkey as an extension to zc.buildout, for
example:

.. code-block:: ini

    [buildout]
    
    extensions =
        mr.developer
        eea.eggmonkey
    
    parts =
        monkey
        ...

Also, you need to add a new part (+ the python26 part, if you don't already
have it):

.. code-block:: ini

    [monkey]
    recipe = zc.recipe.egg
    eggs = eea.eggmonkey
    python = python26

    [python26]
    executable = /usr/bin/python2.6

Usage
-----
Before you use it, you need to run ``bin/buildout`` (or ``bin/develop``) at least once.
This allows eggmonkey to learn about the sources and the packages in
auto-checkout.

After that, you can use the monkey script from bin. Learn about its parameters
by running

*  ``bin/monkey -h``

Typical usage would be:

* ``bin/monkey eea.indicators``

You can specify multiple packages on the command line, they will all be
processed:

* ``bin/monkey eea.indicators eea.workflow eea.version``

Or, if you want to release all eggs specified in the auto-checkout section of
buildout:

* ``bin/monkey -a``

There is a special option that works around bugs in registering the egg with
eggrepos and will run a "python sdist upload" operation, using the -u switch:

* ``bin/monkey -u eea.indicators``

If you're doing manual upload, you may need to specify a different python path,
with the -p switch:

* ``bin/monkey -u eea.indicators -p ~/tools/bin/python``

If you need to specify the path to the mkrelease script, you can give it as an
argument to the script, using the -m switch:

* ``bin/monkey eea.indicators -m /path/to/bin/mkrelease``

If you don't want to specify this path, place the mkrelease script in the PATH
environment variable (typically this can be achieved by activating its
virtualenv).

Finally, if you're releasing eggs to a different repository, or if you have
eggrepo.eea.europa.eu aliased as something different then "eea", you can
manually specify this using the -d switch:

* ``bin/monkey -d eeaeggs eea.indicators``

If you want to forbid all network operations (for example,
during testing), you can run

* ``bin/monkey -n eea.indicators``

If you want to skip versions.cfg update (for example running in a buildout without versions.cfg), you can run

* ``bin/monkey -B eea.indicators``

If you encounter an error in normal operation, you can resume the release process (after manually fixing the problem) with the -R flag

* ``bin/monkey -R 4 eea.indicators``


Providing defaults with a configuration file
============================================
You can write a file ~/.eggmonkey in the following format:

::

    [*]
    python = /path/to/python
    mkrelease = /path/to/mkrelease
    manual_upload = true
    domain = eea

    [eea.indicators]
    domain = eea pypi

This is a ConfigParser file format where each section is a package name, with
the exception of the star (*), which provides defaults for all packages. The
following options can be configured: python, mkrelease, manual_upload and
domain. The domain option can be a space separated list of package repository
aliases where the package will be uploaded.

System requirements
===================
Needs libsvn-dev and libaprutil1-dev (on Debian systems) and apr-util-devel,
subversion-devel on Redhat systems
