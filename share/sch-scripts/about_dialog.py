# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
"""
About dialog.
"""
import gi
from gi.repository import Gtk
import version
gi.require_version('Gtk', '3.0')


class AboutDialog:
    def __init__(self, main_window):
        self.builder = Gtk.Builder()
        self.builder.add_from_file("about_dialog.ui")
        self.dialog = self.builder.get_object("aboutdialog1")
        self.dialog.set_version(version.__version__)
        self.dialog.set_transient_for(main_window)
        self.dialog.run()
        self.dialog.destroy()
