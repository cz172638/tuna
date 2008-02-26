#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-
#   tuna - Application Tuning Gru
#   Copyright (C) 2008 Red Hat Inc.
#
#   This application is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; version 2.
#
#   This application is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   General Public License for more details.

import tuna

def main():
	try:
		app = tuna.tuna()
		app.run()
	except KeyboardInterrupt:
		pass

if __name__ == '__main__':
    main()
