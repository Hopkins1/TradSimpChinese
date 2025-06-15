import sys
import unittest
from pkgutil import iter_modules
from importlib import import_module

from calibre.utils.run_tests import run_cli


def get_tests(module):
    return unittest.defaultTestLoader.loadTestsFromModule(module)


def get_test_suite():
    suite = unittest.TestSuite()
    for module in iter_modules(['tests']):
        module = import_module(
            'calibre_plugins.chinese_text.tests.%s' % module.name)
        suite.addTests(get_tests(module))
    return suite

# To run tests type in a command shell:
#
#        calibre-debug test.py
#
# The test directory must be zipped up with the rest of the code and
# installed into Calibre as a plugin
#
if __name__ == '__main__':
    args = sys.argv[1:]
    patterns = None if len(args) < 1 else ['*%s' % p for p in args]
    unittest.defaultTestLoader.testNamePatterns = patterns
    runner = unittest.TextTestRunner(verbosity=1, failfast=True)
    # result = runner.run(get_test_suite())
    # if not result.wasSuccessful():
    #     exit(1)
    run_cli(get_test_suite(), buffer=False)
