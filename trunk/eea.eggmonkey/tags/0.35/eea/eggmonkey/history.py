from eea.eggmonkey.version import validate_version, _increment_version
from eea.eggmonkey.utils import Error, find_file
import datetime


class HistoryParser(object):
    """A history parser that receives a list of lines in constructor"""

    header = None
    entries = None

    def __init__(self, original):
        self.header   = []
        self.entries  = []
        self.original = original.splitlines()
        section_start = None
        section_end   = None

        header_flag   = True
        for nr, line in enumerate(self.original):
            if line and (line[0].isdigit() or (line[0] == 'r' and 
                                                    line[1].isdigit())):
                if (nr == len(self.original) - 1):  #we test if is last line
                    section_start = nr
                #we test if next line is underlined
                elif self.original[nr+1].strip()[0] in "-=~^":      
                    section_start = nr
                header_flag = False

                #we travel through the file until we find a new section start
                nl = nr + 1
                while nl < len(self.original):
                    if self.original[nl] and (self.original[nl][0].isdigit() or
                            (self.original[nl][0] == 'r' and 
                                    self.original[nl][1].isdigit())):
                        section_end = nl - 1
                        break
                    nl += 1

            if not section_start and header_flag:   
                #if there's no section, this means we have file header
                self.header.append(line)

            if section_start and section_end:   # a section is completed
                self.entries.append(filter(
                                       #we filter empty lines
                                       lambda li:li.strip(), 
                                       self.original[section_start:section_end]))
                section_start = None
                section_end = None

            if section_start and (not section_end) and \
                    (nr == len(self.original) - 1):  
                    #end of file means end of section
                section_end = len(self.original)
                self.entries.append(filter(
                                        #we filter empty lines
                                        lambda li:li.strip(), 
                                   self.original[section_start:section_end]))

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

        newver = _increment_version(version)
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
        f.write("\n".join([l for l in self.header if l.strip()]))
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


def bump_history(path):
    hp = FileHistoryParser(path)
    hp.bump_version()

