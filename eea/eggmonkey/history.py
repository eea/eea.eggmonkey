from eea.eggmonkey.version import validate_version, _increment_version
from eea.eggmonkey.utils import Error, find_file
import datetime


class HistoryParser(object):
    """A history parser that receives a list of lines in constructor"""

    file_header = None
    entries = None

    def __init__(self, original):
        self.file_header   = []
        self.entries  = []
        split_original = original.splitlines()
        section_start = None
        section_end   = None
        is_file_header = True

        is_version_header_line = lambda l: (
                            l and 
                            (l[0].isdigit() or 
                            (l[0] == 'r' and l[1].isdigit())
                        ))  #version header lines start with a number

        is_last_line_in_file = lambda n: n == (len(split_original) - 1)
        is_underlined = lambda n:(len(split_original) - n) >= 2 and \
                                 split_original[n+1].strip() and \
                                 split_original[n+1].strip()[0] in "-=~^"
        get_lines = lambda start, end:filter(lambda li:li.strip(), 
                                             split_original[start:end+1])

        for lineno, line in enumerate(split_original):
            if is_version_header_line(line):
                if is_last_line_in_file(lineno):
                    section_start = lineno
                elif is_underlined(lineno): #we test if next line is underlined
                    section_start = lineno

                    is_file_header = False

                    #we need to know where the section ends
                    #we travel through the file until we find new section start
                    nl = lineno + 1
                    while nl < len(split_original):
                        if is_version_header_line(split_original[nl]):
                            section_end = nl - 1
                            break
                        nl += 1

            if not section_start and is_file_header:   
                #if there's no section, this means we have file header
                self.file_header.append(line)

            if section_start and section_end:   # a section is completed
                self.entries.append(get_lines(section_start, section_end))
                section_start = None
                section_end = None

            if section_start and (not section_end) and \
                                 is_last_line_in_file(lineno): 
                    #end of file means end of section
                section_end = len(split_original)
                self.entries.append(get_lines(section_start, section_end))

    def _create_released_section(self):
        section = self.entries[0]
        header  = section[0]
        version = header.split(" ")[0]
        try:
            validate_version(version)
        except ValueError:
            raise Error("Got invalid version " + version)

        newver     = _increment_version(version)
        today      = str(datetime.datetime.now().date())
        section[0] = u"%s - (%s)" % (newver, today)
        section[1] = u"-" * len(section[0])

    def _create_dev_section(self):
        section = self.entries[0]
        header  = section[0]
        version = header.split(" ")[0]
        try:
            validate_version(version)
        except ValueError:
            raise Error("Got invalid version " + version)

        newver = version
        while "dev" not in newver:
            newver = _increment_version(newver)

        line   = u"%s - (unreleased)" % (newver)

        self.entries.insert(0, [
                line,
                u"-" * len(line)
            ])

    def get_current_version(self):
        """Return the last version"""
        section = self.entries[0]
        header  = section[0]
        version = header.split(" ")[0].strip()
        try:
            validate_version(version)
        except ValueError:
            raise Error("Got invalid version " + version)

        return version


class FileHistoryParser(HistoryParser):
    """A history parser that also does file operations"""

    def __init__(self, path):
        h_path      = find_file(path, "HISTORY.txt")
        self.h_path = h_path
        f           = open(h_path, 'r')
        content     = f.read()
        HistoryParser.__init__(self, content)
        f.close()

    def write(self):
        f = open(self.h_path, 'rw+')
        f.truncate(0); f.seek(0)
        f.write("\n".join([l for l in self.file_header if l.strip()]))
        f.write("\n\n")
        for section in self.entries:
            f.write("\n".join([line for line in section if line.strip()]))
            f.write("\n\n")
        f.close()

    def bump_version(self):
        section = self.entries[0]
        header  = section[0]

        is_dev  = u'unreleased' in header.lower()

        if is_dev:
            self._create_released_section()
        else:
            self._create_dev_section()

        self.write()

    def _make_dev(self):
        """Make the first entry to be at -dev. Used in the devify script

        Returns true if a change needed to be made
        """
        section = self.entries[0]
        header  = section[0]

        is_dev  = "dev" in self.get_current_version()

        if not is_dev:
            self._create_released_section()
            self._create_dev_section()
            self.write()
            return True

        return False

def bump_history(path):
    hp = FileHistoryParser(path)
    hp.bump_version()

