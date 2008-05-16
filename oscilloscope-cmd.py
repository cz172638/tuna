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
	-m, --max_value=MAX_VALUE	MAX_VALUE for the scale
	-S, --snapshot_samples=NR	Take NR samples, a snapshot and exit
	-u, --unit=TYPE			Unit TYPE [Default: us]
'''

def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:],
					   "d:f:hm:S:u:",
					   ("help", "max_value=",
					    "snapshot_samples=",
					    "unit="))
	except getopt.GetoptError, err:
		usage()
		print str(err)
		sys.exit(2)

	max_value = 250
	snapshot_samples = 0
	delimiter = ':'
	field = 2
	ylabel = "Latency"
	unitlabel = "us"

	for o, a in opts:
		if o in ("-d", "--delimiter"):
			delimiter = a
		elif o in ("-f", "--field"):
			field = int(a)
		elif o in ("-h", "--help"):
			usage()
			return
		elif o in ("-m", "--max_value"):
			max_value = int(a)
		elif o in ("-S", "--snapshot_samples"):
			snapshot_samples = int(a)
		elif o in ("-u", "--unit"):
			unitlabel = a
		
	o = oscilloscope.cyclictestoscope(max_value, snapshot_samples,
					  delimiter = delimiter, field = field,
					  ylabel = "%s (%s)" % (ylabel, unitlabel))
	o.run()
	gtk.main()

if __name__ == '__main__':
	main()
