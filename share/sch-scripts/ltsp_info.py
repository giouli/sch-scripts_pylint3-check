# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Show the output of ltsp-info in a dialog.
"""
import re
import textwrap
import gi
from gi.repository import Gtk
import common
gi.require_version('Gtk', '3.0')


class LtspInfo:
    """Show the output of ltsp-info in a dialog."""
    def __init__(self, main_window):
        gladefile = "ltsp_info.ui"
        self.builder = Gtk.Builder()
        self.builder.add_from_file(gladefile)
        self.builder.connect_signals(self)
        self.dialog = self.builder.get_object("dialog1")
        self.dialog.set_transient_for(main_window)
        self.buffer = self.builder.get_object("textbuffer1")
        self.fill()

    def close(self, widget):
        """Closes the dialog."""
        self.dialog.destroy()

    def fill(self):
        """ """
        success, response = common.run_command(['ltsp-info', '-v'])
        self.buffer.set_text(response)
        self.dialog.show()
