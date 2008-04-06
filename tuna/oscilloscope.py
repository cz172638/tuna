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

import gobject, gtk, sys
from matplotlib.backends.backend_gtkagg import \
	FigureCanvasGTKAgg as figure_canvas
import matplotlib.figure, matplotlib.ticker, Numeric

def millisecond_fmt(x, pos = 0):
	ms = x / 1000
	us = x % 1000
	s = "%d" % ms
	if us > 0:
		s += ".%03d" % us
		s = s.rstrip('0')
	s += "ms"

	return s

def microsecond_fmt(x, pos = 0):
	ms = x / 1000
	us = x % 1000
	if int(ms) > 0:
		s = "%d.%03d" % (ms, us)
		s = s.rstrip('0')
		s = s.rstrip('.')
		s += "ms"
	else:
		s = "%dus" % us

	return s

def null_fmt(x, pos = 0):
	return "%d" % x

class histogram_frame(gtk.Frame):
	def __init__(self, title = "Statistics", width = 780, height = 100,
		     max_value = 500, nr_entries = 10, samples_formatter = None,
		     facecolor = "white"):
		gtk.Frame.__init__(self, title)
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
		self.fraction = int(self.max_value / self.nr_entries)

		prefix = "<="
		for bucket in range(self.nr_entries + 1):
			bucket_range = (bucket + 1) * self.fraction
			if bucket_range > self.max_value:
				prefix = ">"
				bucket_range = self.max_value
				
			if samples_formatter:
				text = samples_formatter(bucket_range)
			else:
				text = str(bucket_range)

			label = gtk.Label("%s %s" % (prefix, text))
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
		     ylabel = "Latency", samples_formatter = None):

		gtk.Frame.__init__(self, title)

		font = { 'fontname'   : 'Bitstream Vera Sans',
			 'color'      : 'b',
			 'fontweight' : 'bold',
			 'fontsize'   : 10 }
	
		self.max_value = max_value
		self.nr_samples_on_screen = nr_samples_on_screen
		self.ind = Numeric.arange(nr_samples_on_screen)
		self.samples = [ 0.0 ] * nr_samples_on_screen

		figure = matplotlib.figure.Figure(figsize = (10, 4), dpi = 100,
						  facecolor = facecolor)
		ax = figure.add_subplot(111)
		self.ax = ax
		ax.set_axis_bgcolor(bg_color)

		self.on_screen_samples = ax.plot(self.ind, self.samples, graph_type,
						 color = plot_color)

		ax.set_ylim(0, max_value)
		ax.set_ylabel(ylabel, font)
		ax.set_xlabel("%d samples" % nr_samples_on_screen, font)
		ax.set_xticklabels([])
		if samples_formatter:
			ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(samples_formatter))
		ax.grid(True)

		for label in ax.get_yticklabels():
			label.set(fontsize = 8)

		self.canvas = figure_canvas(figure)  # a gtk.DrawingArea
		self.canvas.set_size_request(width, height)
		
		self.add(self.canvas)
		self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(facecolor))

	def add_sample(self, sample):
		del self.samples[0]
		self.samples.append(sample)
		self.on_screen_samples[0].set_data(self.ind, self.samples)

	def reset(self):
		self.samples = [ 0.0 ] * self.nr_samples_on_screen
		self.on_screen_samples[0].set_data(self.ind, self.samples)

	def refresh(self):
		# Why we need to hide it before redrawing it is a mistery
		# to me, but it works, so, keep this sequence.
		self.canvas.hide()
		self.canvas.draw()
		self.canvas.show()
		return

class oscilloscope(gtk.Window):

	def __init__(self, get_sample = None, width = 800, height = 500,
		     nr_samples_on_screen = 250,
		     graph_type = '-', title = "Osciloscope",
		     max_value = 500, plot_color = "lightgreen",
		     bg_color = "darkgreen", facecolor = "white",
		     ylabel = "Latency",
		     samples_formatter = None):

		gtk.Window.__init__(self)

		self.get_sample = get_sample
		self.max_value = max_value

		self.set_default_size(width, height)
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

		self.min_label = self.__add_table_row(table, 0, "Min")
		self.avg_label = self.__add_table_row(table, 1, "Avg")
		self.max_label = self.__add_table_row(table, 2, "Max")

		help_frame = gtk.Frame("Help")
		help_frame.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(facecolor))

		table = gtk.Table(3, 2, False)
		table.set_border_width(5)
		table.set_row_spacings(5)
		table.set_col_spacings(10)
		help_frame.add(table)

		self.__add_table_row(table, 0, "Space", "Pause")
		self.__add_table_row(table, 1, "R", "Reset")
		self.__add_table_row(table, 2, "Q", "Quit")

		self.scope = oscilloscope_frame("Scope",
						int(width * 0.94),
						int(height * 0.64),
						nr_samples_on_screen,
						max_value = max_value,
						samples_formatter = samples_formatter)

		self.hist = histogram_frame("Histogram", 0, 0, nr_entries = 5,
					    max_value = max_value,
					    samples_formatter = samples_formatter)

		hbox = gtk.HBox()
		hbox.pack_start(stats_frame, False, False)
		hbox.pack_start(self.hist, True, True)
		hbox.pack_end(help_frame, False, False)

		vbox.pack_start(self.scope, True, True)
		vbox.pack_end(hbox, True, False)

		self.show_all()

		self.getting_samples = False
		self.refreshing_screen = False
		self.max = self.min = None
		self.avg = 0
		self.samples_formatter = samples_formatter or null_fmt

	def __add_table_row(self, table, row, label_text, label_value = "0"):
		label = gtk.Label(label_text)
		label.set_use_underline(True)
		label.set_alignment(0, 1)
		table.attach(label, 0, 1, row, row + 1, 0, 0, 0, 0)

		label = gtk.Label(label_value)
		table.attach(label, 1, 2, row, row + 1, 0, 0, 0, 0)
		return label

	def add_sample(self, sample):
		if not self.max or self.max < sample:
			self.max = sample

		if not self.min or self.min > sample:
			self.min = sample

		self.avg = (self.avg + sample) / 2
		self.scope.add_sample(sample)
		self.hist.add_sample(sample)

	def refresh(self):
		if self.max > self.scope.max_value:
			self.scope.max_value *= 2
			self.scope.ax.set_ylim(0, self.scope.max_value)
		self.scope.refresh()
		self.hist.refresh()

	def get_samples(self):
		sample = self.get_sample()
		prev_min, prev_avg, prev_max = self.min, self.avg, self.max

		self.add_sample(sample)

		if self.refreshing_screen:
			if self.min != prev_min:
				self.min_label.set_text(self.samples_formatter(self.min))
			if self.avg != prev_avg:
				self.avg_label.set_text(self.samples_formatter(self.avg))
			if self.max != prev_max:
				self.max_label.set_text(self.samples_formatter(self.max))

			self.refresh()
		return self.getting_samples

	def run(self, interval = 10):
		self.connect("key_press_event", self.key_press_event)
		self.getting_samples = True
		self.refreshing_screen = True
		gobject.timeout_add(interval, self.get_samples)

	def freeze_screen(self, state = False):
		self.refreshing_screen = state

	def stop(self):
		self.getting_samples = False
		self.refreshing_screen = False

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
		elif event.keyval in (ord('r'), ord('R')):
			self.reset()
		elif event.keyval in (ord('q'), ord('Q')):
			gtk.main_quit()

class cyclictestoscope(oscilloscope):
	def __init__(self, max_value):
		oscilloscope.__init__(self, self.get_sample,
				      title = "CyclictestoSCOPE",
				      samples_formatter = microsecond_fmt,
				      nr_samples_on_screen = 500, width = 900,
				      max_value = max_value)

		self.connect("destroy", self.quit)

	def get_sample(self):
		return float(sys.stdin.readline().split(':')[2])

	def quit(self, x):
		gtk.main_quit()

def main():
	try:
		max_value = int(sys.argv[1])
	except:
		max_value = 250

	o = cyclictestoscope(max_value)
	o.run()
	gtk.main()

if __name__ == '__main__':
	main()