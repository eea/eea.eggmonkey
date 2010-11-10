import unittest
from eea.eggmonkey.monkey import _increment_version, validate_version

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



def test_suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(MonkeyTestCase)
    return suite
