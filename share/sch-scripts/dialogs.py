# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Various message dialogs."""

from gi.repository import Gtk

class AskDialog(Gtk.MessageDialog):
    """For the Ask message dialog."""

    def __init__(self, message, title=""):
        super(AskDialog, self).__init__(type=Gtk.MessageType.WARNING,
                                        flags=Gtk.DialogFlags.MODAL,
                                        buttons=Gtk.ButtonsType.YES_NO,
                                        message_format=message)
        self.set_title(title)
        self.set_default_response(Gtk.ResponseType.NO)

    def showup(self):
        """Show the Ask dialog.

        Wait for the user to press a button, close the dialog
        and return the response.
        """
        response = self.run()
        self.destroy()
        return response


class InfoDialog(Gtk.MessageDialog):
    """For the Info message dialog."""

    def __init__(self, message, title=""):
        super(InfoDialog, self).__init__(type=Gtk.MessageType.INFO,
                                         flags=Gtk.DialogFlags.MODAL,
                                         buttons=Gtk.ButtonsType.CLOSE,
                                         message_format=message)
        self.set_title(title)

    def showup(self):
        """Show the Info message dialog.

        Wait for the user to press a button, close the Info message dialog 
        and return the response.
        """
        response = self.run()
        self.destroy()
        return response

class WarningDialog(Gtk.MessageDialog):
    """For the Warning message dialog."""

    def __init__(self, message, title=""):
        super(WarningDialog, self).__init__(type=Gtk.MessageType.WARNING,
                                            flags=Gtk.DialogFlags.MODAL,
                                            buttons=Gtk.ButtonsType.CLOSE,
                                            message_format=message)
        self.set_title(title)

    def showup(self):
        """Show the Warning message dialog.

        Wait for the user to press a button, close the Warning message dialog 
        and return the response.
        """
        response = self.run()
        self.destroy()
        return response

class ErrorDialog(Gtk.MessageDialog):
    """For the Error message dialog."""

    def __init__(self, message, title=""):
        super(ErrorDialog, self).__init__(type=Gtk.MessageType.ERROR,
                                          flags=Gtk.DialogFlags.MODAL,
                                          buttons=Gtk.ButtonsType.CLOSE,
                                          message_format=message)
        self.set_title(title)

    def showup(self):
        """Show the Error message dialog.

        Wait for the user to press a button, close the Error message dialog 
        and return the response.
        """
        response = self.run()
        self.destroy()
        return response
