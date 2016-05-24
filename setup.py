#!/usr/bin/python
from distutils.sysconfig import get_python_lib
from distutils.core import setup
from os.path import isfile, join
import glob
import os

if isfile("MANIFEST"):
	os.unlink("MANIFEST")

# Get PYTHONLIB with no prefix so --prefix installs work.
PYTHONLIB = join(get_python_lib(standard_lib=1, prefix=''), 'site-packages')

setup(name="tuna",
      version = "0.13",
      description = "Application tuning GUI",
      author = "Arnaldo Carvalho de Melo",
      author_email = "acme@redhat.com",
      url = "http://userweb.kernel.org/tuna",
      license = "GPLv2",
      long_description =
"""\
Provides interface for changing scheduler and IRQ tunables, at whole CPU and at per
thread/IRQ level. Allows isolating CPUs for use by a specific application and moving
threads and interrupts to a CPU by just dragging and dropping them.
""",
      packages = ["tuna", "tuna/gui"],
      )
