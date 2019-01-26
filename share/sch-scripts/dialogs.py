# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Various message dialogs."""

from gi.repository import Gtk

class AskDialog(Gtk.MessageDialog):
    """Show an Ask message dialog."""
    
    def __init__(self, message, title=""):
        super(AskDialog, self).__init__(type=Gtk.MessageType.WARNING,
                                        flags=Gtk.DialogFlags.MODAL,
                                        buttons=Gtk.ButtonsType.YES_NO,
                                        message_format=message)
        self.set_title(title)
        self.set_default_response(Gtk.ResponseType.NO)

    def showup(self):
        """Close the Ask dialog and return the response."""
        response = self.run()
        self.destroy()
        return response


class InfoDialog(Gtk.MessageDialog):
    """Show an Info message dialog."""
    
    def __init__(self, message, title=""):
        super(InfoDialog, self).__init__(type=Gtk.MessageType.INFO,
                                         flags=Gtk.DialogFlags.MODAL,
                                         buttons=Gtk.ButtonsType.CLOSE,
                                         message_format=message)
        self.set_title(title)

    def showup(self):
        """Close the Info message dialog and return the response."""
        response = self.run()
        self.destroy()
        return response

class WarningDialog(Gtk.MessageDialog):
    """Show a Warning message dialog."""
    
    def __init__(self, message, title=""):
        super(WarningDialog, self).__init__(type=Gtk.MessageType.WARNING,
                                            flags=Gtk.DialogFlags.MODAL,
                                            buttons=Gtk.ButtonsType.CLOSE,
                                            message_format=message)
        self.set_title(title)

    def showup(self):
        """Close the Warning message dialog and return the response."""
        response = self.run()
        self.destroy()
        return response

class ErrorDialog(Gtk.MessageDialog):
    """Show an Error message dialog."""
    
    def __init__(self, message, title=""):
        super(ErrorDialog, self).__init__(type=Gtk.MessageType.ERROR,
                                          flags=Gtk.DialogFlags.MODAL,
                                          buttons=Gtk.ButtonsType.CLOSE,
                                          message_format=message)
        self.set_title(title)

    def showup(self):
        """Close the Error message dialog and return the response."""
        response = self.run()
        self.destroy()
        return response
