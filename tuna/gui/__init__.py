"""
Copyright (c) 2009  Red Hat Inc.

Application Tuning GUI
"""
__author__ = "Arnaldo Carvalho de Melo <acme@redhat.com>"
__license__ = "GPLv2 License"

DND_TARGET_STRING = 0
DND_TARGET_ROOTWIN = 1

DND_TARGETS = [ ('STRING', 0, DND_TARGET_STRING),
		('text/plain', 0, DND_TARGET_STRING),
		('application/x-rootwin-drop', 0, DND_TARGET_ROOTWIN) ]

from util import *
