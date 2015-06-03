from eea.eggmonkey.utils import Error, find_file
from packaging.version import Version, LegacyVersion, parse


def get_digits(s):
    """Returns only the digits in a string"""
    return int("".join(filter(lambda c:c.isdigit(), s)))


def _increment_version(version):
    """
    """
    if version.endswith('svn'):
        devel = True
        ver = version.split('-')[0].split('.')
    else:
        v_version = Version(version)
        devel = v_version.is_prerelease
        ver = v_version.base_version.split('.')

    release_final = not devel

    ver = map(get_digits, ver)

    last = True #flag for last digit, we treat it differently
    bump = False
    out = []
    length = len(ver)
    i = 0
    for n in reversed(ver):
        n = n + int(not devel and last) + int(bump)
        i += 1
        if n >= 10 and not (i == length):
            n = 0
            bump = True
        else:
            bump = False
        last = False
        out.append(n)

    out = map(str, reversed(out))
    newver = ".".join(out) + (not devel and ".dev0" or "")

    #minor  = int(ver[-1]) + int(not devel)
    #newver = ".".join(ver[:-1]) + ".%s%s" % (minor, (not devel and "-dev" or ""))
    return newver


def bump_version(path):
    """Writes new versions into version file

    It will always go from dev to final and from released to
    increased dev number. Example:

    Called first time:
    1.6.28-dev  =>  1.6.28

    Called second time:
    1.6.28  =>  1.6.29-dev
    """
    v_path = find_file(path, "version.txt")
    f = open(v_path, 'rw+')
    version = f.read().strip()
    version = get_normalized_version(version)

    newver = _increment_version(version)
    f.truncate(0); f.seek(0)
    f.write(newver)
    f.close()


def validate_version(version, legacy=False):
    """See if what we consider a version number is valid version number"""
    version = version.strip()

    if not legacy:
        v_version = parse(version)
        if isinstance(v_version, LegacyVersion):
            raise ValueError

    if "." not in version:
        raise ValueError

    if version.endswith("."):
        raise ValueError

    # all parts need to contain digits, only the last part can contain -dev
    parts = version.split('.')
    parts = [p for p in parts if p != 'eea']
    if not len(parts) > 1:
        raise ValueError

    for part in parts[:-1]:
        for c in part:
            if not c.isdigit():
                raise ValueError

    lp = parts[-1]
    if lp.endswith("dev0"):
        lp = lp.split("dev0")
        if (len(lp) != 2) and (lp[1] == ''):
            raise ValueError
        lp = lp[0]

    for c in lp:
        if not c.isdigit():
            raise ValueError

    return True


def get_normalized_version(version):
    """Normalize the version
    """
    parsed_version = parse(version)

    if isinstance(parsed_version, LegacyVersion):
        try:
            validate_version(version, legacy=True)
        except ValueError:
            raise Error("Got invalid version " + version)

        return version

    return parsed_version.public


def get_version(path):
    """Retrieves the version for a package
    """
    v_path = find_file(path, "version.txt")
    f      = open(v_path, 'r')
    version = f.read().strip()

    return get_normalized_version(version)


def change_version(path, package, version):
    """Changes version in a versions.cfg buildout file
    """
    f = open(path, 'rw+')
    b = []
    _l = "%s = %s\n" % (package, version)

    found = False
    for line in f.readlines():
        p = line.split("=")[0].strip()
        if p == package:
            b.append(_l)
            found = True
        else:
            b.append(line)

    if not found:
        b.append(_l)

    f.truncate(0); f.seek(0)
    f.write("".join(b))
    f.close()

