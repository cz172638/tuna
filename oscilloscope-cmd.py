#!/usr/bin/python
# Arnaldo Carvalho de Melo <acme@redhat.com>
#
# Please check the tuna repository at:
# http://git.kernel.org/?p=linux/kernel/git/acme/tuna.git;a=tree
# For newer versions and to see it integrated with tuna
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation;
# version 2.1 of the License.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

import getopt, sys, gtk
from tuna import oscilloscope

def usage():
	print '''Usage: oscilloscope [OPTIONS]
	-h, --help			Give this help list
	-d, --delimiter=CHARACTER	CHARACTER used as a delimiter [Default: :]
	-f, --field=FIELD		FIELD to plot [Default: 2]
	-g, --geometry=GEOMETRY         X geometry specification (see "X" man page)
	-m, --max_value=MAX_VALUE	MAX_VALUE for the scale
	-M, --sample_multiplier=VALUE	VALUE to multiply each sample
	-n, --noscale			Do not scale when a sample is > MAX_SCALE
	-s, --nr_samples_on_screen=NR	Show NR samples on screen
	-S, --snapshot_samples=NR	Take NR samples, a snapshot and exit
	-u, --unit=TYPE			Unit TYPE [Default: us]
'''

def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:],
					   "d:f:g:hM:m:ns:S:u:",
					   ("geometry=",
					    "help", "max_value=",
					    "sample_multiplier=",
					    "noscale",
					    "nr_samples_on_screen=",
					    "snapshot_samples=",
					    "unit="))
	except getopt.GetoptError, err:
		usage()
		print str(err)
		sys.exit(2)

	max_value = 250
	sample_multiplier = 1
	snapshot_samples = 0
	delimiter = ':'
	field = 2
	ylabel = "Latency"
	unitlabel = "us"
	geometry = None
	scale = True
	nr_samples_on_screen = 250

	for o, a in opts:
		if o in ("-d", "--delimiter"):
			delimiter = a
		elif o in ("-f", "--field"):
			field = int(a)
		elif o in ("-g", "--geometry"):
			geometry = a
		elif o in ("-h", "--help"):
			usage()
			return
		elif o in ("-m", "--max_value"):
			max_value = int(a)
		elif o in ("-M", "--sample_multiplier"):
			sample_multiplier = float(a)
		elif o in ("-n", "--noscale"):
			scale = False
		elif o in ("-s", "--nr_samples_on_screen"):
			nr_samples_on_screen = int(a)
		elif o in ("-S", "--snapshot_samples"):
			snapshot_samples = int(a)
		elif o in ("-u", "--unit"):
			unitlabel = a

	o = oscilloscope.cyclictestoscope(max_value, snapshot_samples,
					  nr_samples_on_screen = nr_samples_on_screen,
					  delimiter = delimiter, field = field,
					  ylabel = "%s (%s)" % (ylabel, unitlabel),
					  geometry = geometry, scale = scale,
					  sample_multiplier = sample_multiplier)
	o.run()
	gtk.main()

if __name__ == '__main__':
	main()
