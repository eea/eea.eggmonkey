import unittest
from eea.eggmonkey.monkey import _increment_version, validate_version, HistoryParser
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

"""


class MonkeyTestCase(unittest.TestCase):

    def test_increment(self):
        assert _increment_version("1.0"), "1.1-dev"
        assert _increment_version("1.0-dev"), "1.0"
        assert _increment_version("1.0dev"), "1.0"
        assert _increment_version("0.1svn"), "0.1"

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
        assert len(es) == 3
        assert len(es[0]) == 3
        assert len(es[1]) == 4
        assert len(es[2]) == 3

def test_suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(MonkeyTestCase)
    return suite

if __name__ == "__main__":
    unittest.main()
