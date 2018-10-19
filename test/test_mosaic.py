import unittest
import matplotlib as mpl
mpl.use('TkAgg')
from os import path

from apercal.modules.mosaic import mosaic

here = path.dirname(__file__)


class TestMosaic(unittest.TestCase):

    def test_mosaic(self):
        p = mosaic(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '..')
        p.basedir = path.join(here, '../data/small')
        p.show(showall=False)
        p.go()
