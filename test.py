"""Load tests"""
import doctest
import unittest
from snowballing import dbindex, utils, models, config, operations, snowballing
from snowballing import jupyter_utils, approaches, strategies, config_helpers
from snowballing import collection_helpers
from pathlib import Path
from snowballing.example import database


flags = doctest.REPORT_ONLY_FIRST_FAILURE
suites = []
suites.append(doctest.DocTestSuite(dbindex, optionflags=flags))
suites.append(doctest.DocTestSuite(utils, optionflags=flags))
suites.append(doctest.DocTestSuite(models, optionflags=flags))
suites.append(doctest.DocTestSuite(operations, optionflags=flags))
suites.append(doctest.DocTestSuite(config_helpers, optionflags=flags))
suites.append(doctest.DocTestSuite(snowballing, optionflags=flags))
suites.append(doctest.DocTestSuite(jupyter_utils, optionflags=flags))
suites.append(doctest.DocTestSuite(approaches, optionflags=flags))
suites.append(doctest.DocTestSuite(strategies, optionflags=flags))
suites.append(doctest.DocTestSuite(collection_helpers, optionflags=flags))
suites.append(doctest.DocTestSuite(config, optionflags=flags))

def load_tests(loader, tests, pattern):
    """Create test suite"""
    # pylint: disable=unused-argument
    suite = unittest.TestSuite()
    for test_suite in suites:
        suite.addTest(test_suite)
    return suite


if __name__ == "__main__":
    unittest.main()
