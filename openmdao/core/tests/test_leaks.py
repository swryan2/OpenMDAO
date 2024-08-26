
import unittest
from io import StringIO

import openmdao.api as om
from openmdao.core.tests.test_coloring import run_opt
from openmdao.utils.general_utils import set_pyoptsparse_opt
from openmdao.devtools.memory import check_iter_leaks, list_iter_leaks
from openmdao.utils.testing_utils import use_tempdirs

try:
    import objgraph
except ImportError:
    objgraph = None


OPT, OPTIMIZER = set_pyoptsparse_opt('SNOPT', fallback=True)


def run_opt_wrapper(driver_class, optimizer):
    def _wrapper():
        run_opt(driver_class, 'auto', optimizer=optimizer,
                dynamic_total_coloring=True, partial_coloring=True)
    return _wrapper


@unittest.skipUnless(objgraph is not None, "Test requires objgraph to be installed. (pip install objgraph).")
@use_tempdirs
class LeakTestCase(unittest.TestCase):

    ISOLATED = True

    @unittest.skipIf(OPTIMIZER is None, 'pyoptsparse SLSQP is not installed.')
    def test_leaks_pyoptsparse_slsqp(self):
        lst = check_iter_leaks(4, run_opt_wrapper(om.pyOptSparseDriver, 'SLSQP'))
        if lst:
            msg = StringIO()
            list_iter_leaks(lst, msg)
            self.fail(msg.getvalue())

    @unittest.skipUnless(OPTIMIZER == 'SNOPT', 'pyoptsparse SNOPT is not installed.')
    def test_leaks_pyoptsparse_snopt(self):
        lst = check_iter_leaks(4, run_opt_wrapper(om.pyOptSparseDriver, 'SNOPT'))
        if lst:
            msg = StringIO()
            list_iter_leaks(lst, msg)
            self.fail(msg.getvalue())

    def test_leaks_scipy_slsqp(self):
        lst = check_iter_leaks(4, run_opt_wrapper(om.ScipyOptimizeDriver, 'SLSQP'))
        if lst:
            msg = StringIO()
            list_iter_leaks(lst, msg)
            self.fail(msg.getvalue())


if __name__ == '__main__':
    unittest.main()
