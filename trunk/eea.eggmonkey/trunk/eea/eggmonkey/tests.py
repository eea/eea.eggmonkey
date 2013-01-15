from eea.eggmonkey.history import HistoryParser
from eea.eggmonkey.version import _increment_version, validate_version
import os
import shutil
import subprocess
import sys
import time
import unittest
#import pprint


H1 = """Changelog
==========

1.0 - (10-20-2008)
------------------
 * some entry

"""

H2 = """Changelog
==========

1.1 - (10-20-2008)
------------------
 * some entry

1.0 - (10-19-2008)
------------------

 * something

 * or other

0.9 - (9-20-2008)
-----------------
 * and something else

r234 - (8-20-2008)
-----------------
 * entry 1
 * entry 2

r235 - (7-20-2008)
-----------------
 r3456 - entry A
 * entry B
 r3456 - entry C
 r3457 - entry D
 * entry E

 """

H3 = """Changelog
==========
1.1 - (10-20-2008)
------------------
 * some entry
1.0 - (10-19-2008)
------------------
 * something
 * or other
0.9 - (9-20-2008)
-----------------
 * and something else
"""

H4 = """\xefChangelog
==========

1.0 - (10-20-2008)
------------------
 * some entry

"""

class MonkeyTestCase(unittest.TestCase):

    def test_increment(self):
        assert _increment_version("1.0") == "1.1-dev"
        assert _increment_version("1.0-dev") == "1.0"
        assert _increment_version("1.0dev") == "1.0"
        assert _increment_version("0.1svn") == "0.1"

        print _increment_version("0.9.9-dev")

        assert _increment_version("0.9") == "1.0-dev"
        assert _increment_version("0.0.1") == "0.0.2-dev"
        assert _increment_version("0.0.1-dev") == "0.0.1"
        assert _increment_version("0.0.9") == "0.1.0-dev"
        assert _increment_version("0.9.9") == "1.0.0-dev"
        assert _increment_version("0.9.9-dev") == "0.9.9"

    def test_validate_version(self):

        #raises error when there are problems with the dots
        self.assertRaises(ValueError, validate_version, "1")
        self.assertRaises(ValueError, validate_version, "1.")
        self.assertRaises(ValueError, validate_version, "1.2.")

        #raises errors when there are weird characters in parts
        self.assertRaises(ValueError, validate_version, "1svn.3")
        self.assertRaises(ValueError, validate_version, "1svn.3-dev")
        self.assertRaises(ValueError, validate_version, "1-dev.0")
        self.assertRaises(ValueError, validate_version, "1.0-dev.0")

    def test_history_parser(self):
        hp = HistoryParser(H1)
        assert hp.get_current_version() == "1.0"

        hp = HistoryParser(H2)
        es = hp.entries
        assert len(es) == 5
        assert len(es[0]) == 3
        assert len(es[1]) == 4
        assert len(es[2]) == 3

        hp = HistoryParser(H3)
        es = hp.entries
        assert len(es) == 3
        assert len(es[0]) == 3
        assert len(es[1]) == 4
        assert len(es[2]) == 3

    def test_bom(self):
        """sometimes file start with a BOM, we strip it
        """
        hp = HistoryParser(H4)
        assert hp.file_header[0][0] != 'xef'
        

def test_suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(MonkeyTestCase)
    return suite

if __name__ == "__main__":
    unittest.main()
