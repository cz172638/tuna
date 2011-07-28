# Oscilloscope
#
# Copyright 2008-2009 Red Hat, Inc.
# 
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

import gobject, gtk, os, sys
from matplotlib.backends.backend_gtkagg import \
	FigureCanvasGTKAgg as figure_canvas
import matplotlib.figure, matplotlib.ticker, numpy

class histogram_frame(gtk.Frame):
	def __init__(self, title = "Statistics", width = 780, height = 100,
		     max_value = 500, nr_entries = 10,
		     facecolor = "white"):
		gtk.Frame.__init__(self, title)

		self.fraction = int(max_value / nr_entries)
		if self.fraction == 0:
			self.fraction = max_value
			nr_entries = 1
		self.max_value = max_value
		self.nr_entries = nr_entries
		self.nr_samples = 0

		table = gtk.Table(3, self.nr_entries + 1, False)
		table.set_border_width(5)
		table.set_row_spacings(5)
		table.set_col_spacings(10)
		self.add(table)
		self.buckets = [ 0, ] * (nr_entries + 1)
		self.buckets_bar = [ None, ] * (nr_entries + 1)
		self.buckets_counter = [ None, ] * (nr_entries + 1)

		prefix = "<="
		for bucket in range(self.nr_entries + 1):
			bucket_range = (bucket + 1) * self.fraction
			if bucket_range > self.max_value:
				prefix = ">"
				bucket_range = self.max_value

			label = gtk.Label("%s %d" % (prefix, bucket_range))
			label.set_alignment(0, 1)
			table.attach(label, 0, 1, bucket, bucket + 1, 0, 0, 0, 0)

			self.buckets_bar[bucket] = gtk.ProgressBar()
			table.attach(self.buckets_bar[bucket], 1, 2, bucket, bucket + 1, 0, 0, 0, 0)

			self.buckets_counter[bucket] = gtk.Label("0")
			label.set_alignment(0, 1)
			table.attach(self.buckets_counter[bucket], 2, 3, bucket, bucket + 1, 0, 0, 0, 0)

		self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(facecolor))

	def add_sample(self, sample):
		if sample > self.max_value:
			bucket = self.nr_entries
		else:
			bucket = int(sample / self.fraction)
		self.nr_samples += 1
		self.buckets[bucket] += 1

	def refresh(self):
		for bucket in range(self.nr_entries + 1):
			self.buckets_counter[bucket].set_text(str(self.buckets[bucket]))
			fraction = float(self.buckets[bucket]) / self.nr_samples
			self.buckets_bar[bucket].set_fraction(fraction)

	def reset(self):
		self.buckets = [ 0, ] * (self.nr_entries + 1)
		self.nr_samples = 0

class oscilloscope_frame(gtk.Frame):

	def __init__(self, title = "Osciloscope", width = 780, height = 360,
		     nr_samples_on_screen = 250, graph_type = '-',
		     max_value = 500, plot_color = "lightgreen",
		     bg_color = "darkgreen", facecolor = "white",
		     ylabel = "Latency", picker = None):

		gtk.Frame.__init__(self, title)

		self.font = { 'fontname'   : 'Liberation Sans',
			      'color'      : 'b',
			      'fontweight' : 'bold',
			      'fontsize'   : 10 }

		self.max_value = max_value
		self.nr_samples_on_screen = nr_samples_on_screen
		self.ind = numpy.arange(nr_samples_on_screen)
		self.samples = [ 0.0 ] * nr_samples_on_screen

		figure = matplotlib.figure.Figure(figsize = (10, 4), dpi = 100,
						  facecolor = facecolor)
		ax = figure.add_subplot(111)
		self.ax = ax
		ax.set_axis_bgcolor(bg_color)

		self.on_screen_samples = ax.plot(self.ind, self.samples, graph_type,
						 color = plot_color,
						 picker = picker)

		ax.set_ylim(0, max_value)
		ax.set_ylabel(ylabel, self.font)
		ax.set_xlabel("%d samples" % nr_samples_on_screen, self.font)
		ax.set_xticklabels([])
		ax.grid(True)

		for label in ax.get_yticklabels():
			label.set(fontsize = 8)

		self.canvas = figure_canvas(figure)  # a gtk.DrawingArea
		self.canvas.set_size_request(width, height)

		self.add(self.canvas)
		self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(facecolor))
		self.nr_samples = 0

	def add_sample(self, sample):
		del self.samples[0]
		self.samples.append(sample)
		self.on_screen_samples[0].set_data(self.ind, self.samples)
		self.nr_samples += 1
		if self.nr_samples <= self.nr_samples_on_screen:
			self.ax.set_xlabel("%d samples" % self.nr_samples, self.font)

	def reset(self):
		self.samples = [ 0.0 ] * self.nr_samples_on_screen
		self.nr_samples = 0
		self.on_screen_samples[0].set_data(self.ind, self.samples)

	def refresh(self):
		self.canvas.draw()
		return

def add_table_row(table, row, label_text, label_value = "0"):
	label = gtk.Label(label_text)
	label.set_use_underline(True)
	label.set_alignment(0, 1)
	table.attach(label, 0, 1, row, row + 1, 0, 0, 0, 0)

	label = gtk.Label(label_value)
	table.attach(label, 1, 2, row, row + 1, 0, 0, 0, 0)
	return label

class system_info_frame(gtk.Frame):
	def __init__(self, title = "System", facecolor = "white"):
		gtk.Frame.__init__(self, title)

		self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(facecolor))

		table = gtk.Table(3, 2, False)
		table.set_border_width(5)
		table.set_row_spacings(5)
		table.set_col_spacings(10)
		self.add(table)

		u = os.uname()
		add_table_row(table, 0, "Kernel Release", u[2])
		add_table_row(table, 1, "Architecture", u[4])
		add_table_row(table, 2, "Machine", u[1])

class oscilloscope(gtk.Window):

	def __init__(self, get_sample = None, width = 800, height = 500,
		     nr_samples_on_screen = 250,
		     graph_type = '-', title = "Osciloscope",
		     max_value = 500, plot_color = "lightgreen",
		     bg_color = "darkgreen", facecolor = "white",
		     ylabel = "Latency",
		     picker = None,
		     snapshot_samples = 0,
		     geometry = None, scale = True):

		gtk.Window.__init__(self)
		if geometry:
			self.parse_geometry(geometry)
			width, height = self.get_size()
		else:
			self.set_default_size(width, height)

		self.get_sample = get_sample
		self.max_value = max_value
		self.snapshot_samples = snapshot_samples
		self.scale = scale

		self.set_title(title)

		vbox = gtk.VBox()
		vbox.set_border_width(8)
		self.add(vbox)

		stats_frame = gtk.Frame("Statistics")
		stats_frame.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(facecolor))

		table = gtk.Table(3, 2, False)
		table.set_border_width(5)
		table.set_row_spacings(5)
		table.set_col_spacings(10)
		stats_frame.add(table)

		self.min_label = add_table_row(table, 0, "Min")
		self.avg_label = add_table_row(table, 1, "Avg")
		self.max_label = add_table_row(table, 2, "Max")

		help_frame = gtk.Frame("Help")
		help_frame.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(facecolor))

		table = gtk.Table(4, 2, False)
		table.set_border_width(5)
		table.set_row_spacings(5)
		table.set_col_spacings(10)
		help_frame.add(table)

		add_table_row(table, 0, "Space", "Pause")
		add_table_row(table, 1, "S", "Snapshot")
		add_table_row(table, 2, "R", "Reset")
		add_table_row(table, 3, "Q", "Quit")

		self.scope = oscilloscope_frame("Scope",
						int(width * 0.94),
						int(height * 0.64),
						nr_samples_on_screen,
						max_value = max_value,
						graph_type = graph_type,
						picker = picker,
						ylabel = ylabel)

		self.hist = histogram_frame("Histogram", 0, 0, nr_entries = 5,
					    max_value = max_value)

		info_frame = system_info_frame()

		vbox_help_info = gtk.VBox()
		vbox_help_info.pack_start(info_frame, False, False)
		vbox_help_info.pack_end(help_frame, False, False)
		hbox = gtk.HBox()
		hbox.pack_start(vbox_help_info, False, False)
		hbox.pack_start(stats_frame, False, False)
		hbox.pack_end(self.hist, True, True)

		vbox.pack_start(self.scope, True, True)
		vbox.pack_end(hbox, True, False)

		self.show_all()

		self.getting_samples = False
		self.refreshing_screen = False
		self.max = self.min = None
		self.avg = 0

	def add_sample(self, sample):
		if not self.max or self.max < sample:
			self.max = sample

		if not self.min or self.min > sample:
			self.min = sample

		self.avg = (self.avg + sample) / 2
		self.scope.add_sample(sample)
		self.hist.add_sample(sample)

	def refresh(self):
		if self.scale and self.max > self.scope.max_value:
			self.scope.max_value *= 2
			self.scope.ax.set_ylim(0, self.scope.max_value)
		self.scope.refresh()
		self.hist.refresh()
		while gtk.events_pending():
			gtk.main_iteration()

	def get_samples(self, fd, condition):
		try:
			sample = self.get_sample()
			prev_min, prev_avg, prev_max = self.min, self.avg, self.max

			self.add_sample(sample)

			if self.refreshing_screen:
				if self.min != prev_min:
					self.min_label.set_text("%-6.3f" % self.min)
				if self.avg != prev_avg:
					self.avg_label.set_text("%-6.3f" % self.avg)
				if self.max != prev_max:
					self.max_label.set_text("%-6.3f" % self.max)

				self.refresh()

			if self.snapshot_samples == self.scope.nr_samples:
				self.snapshot()
				gtk.main_quit()
		except:
			print "invalid sample, check the input format"
			pass
		return self.getting_samples

	def run(self, fd):
		self.connect("key_press_event", self.key_press_event)
		self.getting_samples = True
		self.refreshing_screen = True
		gobject.io_add_watch(fd, gobject.IO_IN | gobject.IO_PRI,
				     self.get_samples)

	def freeze_screen(self, state = False):
		self.refreshing_screen = state

	def stop(self):
		self.getting_samples = False
		self.refreshing_screen = False

	def snapshot(self):
		self.scope.canvas.print_figure("scope_snapshot.svg")

	def reset(self):
		self.scope.max_value = self.max_value
		self.scope.ax.set_ylim(0, self.scope.max_value)
		self.scope.reset()
		self.hist.reset()
		self.min = self.max_value
		self.max = 0
		self.avg = 0

	def key_press_event(self, widget, event):
		if event.keyval == ord(' '):
			self.freeze_screen(not self.refreshing_screen)
		elif event.keyval in (ord('s'), ord('S')):
			self.snapshot()
		elif event.keyval in (ord('r'), ord('R')):
			self.reset()
		elif event.keyval in (ord('q'), ord('Q')):
			gtk.main_quit()

class ftrace_window(gtk.Window):

	(COL_FUNCTION, ) = range(1)

	def __init__(self, trace, parent = None):
		gtk.Window.__init__(self)
		try:
			self.set_screen(parent.get_screen())
		except AttributeError:
			self.connect('destroy', lambda *w: gtk.main_quit())

        	self.set_border_width(8)
		self.set_default_size(350, 500)
		self.set_title("ftrace")

		vbox = gtk.VBox(False, 8)
		self.add(vbox)

		sw = gtk.ScrolledWindow()
		sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
		sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		vbox.pack_start(sw, True, True)

		store = gtk.ListStore(gobject.TYPE_STRING)

		for entry in trace:
			if entry[0] in [ "#", "\n" ] or entry[:4] == "vim:":
				continue
			iter = store.append()
			store.set(iter, self.COL_FUNCTION, entry.strip())

		treeview = gtk.TreeView(store)
		treeview.set_rules_hint(True)

		column = gtk.TreeViewColumn("Function", gtk.CellRendererText(),
					    text = self.COL_FUNCTION)
		treeview.append_column(column)

		sw.add(treeview)
		self.show_all()

class cyclictestoscope(oscilloscope):
	def __init__(self, max_value, snapshot_samples = 0, nr_samples_on_screen = 500,
		     delimiter = ':', field = 2, ylabel = "Latency",
		     geometry = None, scale = True, sample_multiplier = 1):
		oscilloscope.__init__(self, self.get_sample,
				      title = "CyclictestoSCOPE",
				      nr_samples_on_screen = nr_samples_on_screen,
				      width = 900, max_value = max_value,
				      picker = self.scope_picker,
				      snapshot_samples = snapshot_samples,
				      ylabel = ylabel, geometry = geometry,
				      scale = scale)

		self.connect("destroy", self.quit)
		self.delimiter = delimiter
		self.sample_multiplier = sample_multiplier
		self.field = field
		self.latency_tracer = os.access("/sys/kernel/debug/tracing/trace", os.R_OK)
		if self.latency_tracer:
			self.traces = [ None, ] * nr_samples_on_screen

	def scope_picker(self, line, mouseevent):
		if (not self.latency_tracer) or mouseevent.xdata is None:
			return False, dict()

		x = int(mouseevent.xdata)
		if self.traces[x]:
			fw = ftrace_window(self.traces[x], self)
		return False, dict()

	def get_sample(self):
		fields = sys.stdin.readline().split(self.delimiter)
		try:
			sample = float(fields[self.field]) * self.sample_multiplier
		except:
			print "fields=%s, self.field=%s,self.delimiter=%s" % (fields, self.field, self.delimiter)
			return None

		if self.latency_tracer:
			del self.traces[0]
			if sample > self.avg:
				print sample
				try:
					f = file("/sys/kernel/debug/tracing/trace")
					trace = f.readlines()
					f.close()
					f = file("/sys/kernel/debug/tracing/tracing_max_latency", "w")
					f.write("0\n")
					f.close()
				except:
					trace = None
			else:
				print "-"
				trace = None

			self.traces.append(trace)

		return sample

	def run(self):
		oscilloscope.run(self, sys.stdin.fileno())

	def quit(self, x):
		gtk.main_quit()
