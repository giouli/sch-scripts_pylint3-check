#!/usr/bin/env python3
# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Sch-scripts."""

import getpass
import glob
import locale
import os
import socket
import subprocess
import sys
import gi
from gi.repository import Gtk

from dbus.mainloop.glib import DBusGMainLoop
from twisted.internet import gtk3reactor
from twisted.internet import reactor, defer
import about_dialog
import common
import config
import create_users
import dialogs
import export_dialog
import group_form
import import_dialog
import ip_dialog
import libuser
import ltsp_info
import maintenance
import parsers
import shared_folders
import user_form
import version
DBusGMainLoop(set_as_default=True)
gtk3reactor.install()
gi.require_version('Gtk', '3.0')


class Gui:
    def __init__(self):
        self.system = libuser.SYSTEM
        self.shared_fold = shared_folders.SharedFolders(self.system)
        self.conf = config.PARSER
        self.builder = Gtk.Builder()
        self.builder.add_from_file('sch-scripts.ui')
        self.builder.connect_signals(self)

        self.main_window = self.builder.get_object('main_window')
        self.users_tree = self.builder.get_object('users_treeview')
        self.groups_tree = self.builder.get_object('groups_treeview')
        self.users_sort = self.builder.get_object('users_sort')
        self.groups_sort = self.builder.get_object('groups_sort')
        self.users_filter = self.builder.get_object('users_filter')
        self.groups_filter = self.builder.get_object('groups_filter')
        self.users_model = self.builder.get_object('users_store')
        self.groups_model = self.builder.get_object('groups_store')

        self.show_private_groups = False
        self.show_system_groups = False
        self.builder.get_object('mi_show_private_groups').set_active(self.conf.getboolean('GUI', 'show_private_groups'))
        self.builder.get_object('mi_show_system_groups').set_active(self.conf.getboolean('GUI', 'show_system_groups'))

        self.users_filter.set_visible_func(self.set_user_visibility)
        self.groups_filter.set_visible_func(self.set_group_visibility)

        # Fill the View -> Columns menu with all the columns of the treeview
        mn_view_columns = self.builder.get_object('mn_view_columns')
        users_columns = self.users_tree.get_columns()

        visible = self.conf.get('GUI', 'visible_user_columns')
        if visible == 'all':
            visible = [c.get_title() for c in users_columns]
        else:
            visible = visible.split(',')
        for column in users_columns:
            title = column.get_title()
            menuitem = Gtk.CheckMenuItem(title)
            menuitem.connect('toggled', self.on_mi_view_column_toggled, column)
            menuitem.set_active(title in visible)
            mn_view_columns.append(menuitem)
        self.populate_treeviews()

        self.queue = []
        self.system.connect_event(self.on_libuser_changed)
        self.main_window.show_all()

## General helper functions

    @classmethod
    def edit_file(cls, filename):
        """Function for editing a file."""
        subprocess.Popen(['xdg-open', filename], stdin=open(os.devnull))
        # TODO: Maybe throw an error message if not os.path.isfile(filename)

    @classmethod
    def run_as_sudo_user(cls, cmd):
        print('EXECUTE:\t' + '\t'.join(cmd))
        sys.stdout.flush()

    def open_link(self, link):
        self.run_as_sudo_user(['xdg-open', link])

    def get_selected_users(self):
        """Function for returning selected users."""
        selection = self.users_tree.get_selection()
        paths = selection.get_selected_rows()[1]
        selected = [self.users_sort[path][0] for path in paths]
        return selected

    def get_selected_groups(self):
        """Function for returning selected groups."""
        selection = self.groups_tree.get_selection()
        paths = selection.get_selected_rows()[1]
        selected = [self.groups_sort[path][0] for path in paths]
        return selected

## INotify

    def on_libuser_changed(self, _event):
        self.queue.append(_event)
        dif = defer.Deferred()
        reactor.callLater(1, dif.callback, len(self.queue))
        dif.addCallback(self.check_libuser_events)

    def check_libuser_events(self, len_queue):
        if len_queue == len(self.queue):
            self.queue = []
            self.repopulate_treeviews()

## Groups and users treeviews

    def populate_treeviews(self):
        """Fill the users and groups treeviews from the system."""
        for user in self.system.users.values():
            self.users_model.append([user, user.uid, user.name, user.primary_group, user.rname, user.office, user.wphone, user.hphone, user.other, user.directory, user.shell, user.lstchg, user.min, user.max, user.warn, user.inact, user.expire])
        for group in self.system.groups.values():
            self.groups_model.append([group, group.gid, group.name])

    def repopulate_treeviews(self):
        """Repopulate treeviews.

        Preserve the selected groups and users, clear and refill the treeviews
        and reselect the previously selected groups and users, if possible.
        """
        groups_selection = self.groups_tree.get_selection()
        users_selection = self.users_tree.get_selection()
        selected_groups = [i.name for i in self.get_selected_groups()]
        selected_users = [i.name for i in self.get_selected_users()]

        # Clear and refill the treeviews
        self.users_model.clear()
        self.groups_model.clear()
        self.populate_treeviews()

        # Reselect the previously selected groups and users, if possible
        groups_iters = dict((row[0].name, row.iter) for row in self.groups_sort)
        for gname in selected_groups:
            if gname in groups_iters:
                groups_selection.select_iter(groups_iters[gname])
        users_iters = dict((row[0].name, row.iter) for row in self.users_sort)
        for uname in selected_users:
            if uname in users_iters:
                users_selection.select_iter(users_iters[uname])

    def set_user_visibility(self, model, rowiter, _options):
        """Set if a user is visible."""
        user = model[rowiter][0]
        selected = self.get_selected_groups()
        # FIXME: The list comprehension here costs
        return (len(selected) == 0 and (self.show_system_groups or not user.is_system_user())) \
                or user in [u for g in selected for u in g.members.values()]

    def set_group_visibility(self, model, rowiter, _options):
        """Set if a group is private."""
        group = model[rowiter][0]
        return (self.show_private_groups or not group.is_private()) and (self.show_system_groups or group.is_user_group())

    def on_groups_selection_changed(self, selection):
        """Edit selected group."""
        self.users_filter.refilter()
        mi_edit_group = self.builder.get_object('mi_edit_group')
        mi_delete_group = self.builder.get_object('mi_delete_group')
        rows = selection.count_selected_rows()
        if rows == 0:
            mi_edit_group.set_sensitive(False)
            mi_delete_group.set_sensitive(False)
        elif rows == 1:
            mi_edit_group.set_sensitive(True)
            mi_edit_group.set_label('Επεξεργασία ομάδας...')
            mi_delete_group.set_label('Διαγραφή ομάδας...')
            mi_delete_group.set_sensitive(True)
        else:
            mi_edit_group.set_sensitive(False)
            mi_delete_group.set_label('Διαγραφή ομάδων...')
            mi_delete_group.set_sensitive(True)

    def on_users_selection_changed(self, selection):
        """Edit selected user."""
        mi_edit_user = self.builder.get_object('mi_edit_user')
        mi_delete_user = self.builder.get_object('mi_delete_user')
        mi_remove_user = self.builder.get_object('mi_remove_user')
        rows = selection.count_selected_rows()
        if rows == 0:
            mi_edit_user.set_sensitive(False)
            mi_delete_user.set_sensitive(False)
            mi_remove_user.set_sensitive(False)
        else:
            if self.groups_tree.get_selection().count_selected_rows() > 0:
                mi_remove_user.set_sensitive(True)
            else:
                mi_remove_user.set_sensitive(False)

            mi_delete_user.set_sensitive(True)

            if rows == 1:
                mi_edit_user.set_sensitive(True)
                mi_edit_user.set_label('Επεξεργασία χρήστη...')
                mi_delete_user.set_label('Διαγραφή χρήστη...')
            else:
                mi_edit_user.set_sensitive(False)
                mi_delete_user.set_label('Διαγραφή χρηστών...')


    def on_users_tv_button_press_event(self, _widget, _event):
        clicked = _widget.get_path_at_pos(int(_event.x), int(_event.y))

        if _event.button == 3:
            _menu = self.builder.get_object('mn_users').popup(None, None, None, None, _event.button, _event.time)
            selection = _widget.get_selection()
            selected = selection.get_selected_rows()[1]
            if clicked:
                clicked = clicked[0]
                if clicked not in selected:
                    selection.unselect_all()
                    selection.select_path(clicked)
            else:
                selection.unselect_all()
            return True

    def on_groups_tv_button_press_event(self, _widget, _event):
        clicked = _widget.get_path_at_pos(int(_event.x), int(_event.y))

        if _event.button == 3:
            _menu = self.builder.get_object('mn_groups').popup(None, None, None, None, _event.button, _event.time)
            selection = _widget.get_selection()
            selected = selection.get_selected_rows()[1]
            if clicked:
                clicked = clicked[0]
                if clicked not in selected:
                    selection.unselect_all()
                    selection.select_path(clicked)
            else:
                selection.unselect_all()
            return True

    def on_users_treeview_row_activated(self, _widget, path, _column):
        user_form.EditUserDialog(self.system, _widget.get_model()[path][0])

    def on_groups_treeview_row_actv(self, _widget, path, _column):
        group_form.EditGroupDialog(self.system, self.shared_fold, _widget.get_model()[path][0])

    def on_unselect_all_groups_clicked(self, _widget):
        self.groups_tree.get_selection().unselect_all()

    def on_main_window_delete_event(self, _widget, _event):
        self.conf.set('GUI', 'show_private_groups', str(self.show_private_groups))
        self.conf.set('GUI', 'show_system_groups', str(self.show_system_groups))
        visible_cols = [col.get_title() for col in self.users_tree.get_columns() if col.get_visible()]
        self.conf.set('GUI', 'visible_user_columns', ','.join(visible_cols))
        config.save()
        exit()

## File menu

    @classmethod
    def on_mi_signup_activate(cls, _widget):
        subprocess.Popen(['./signup_server.py'])

    #FIXME: Maybe use notify /etc/group then self.populate_treeviews not need to
    #update user groups for shared folder library
    def on_mi_new_users_activate(self, _widget):
        create_users.NewUsersDialog(self.system, self.shared_fold)

    @classmethod
    def on_mi_import_passwd_activate(cls, _widget):
        """Import password file dialog."""
        chooser = Gtk.FileChooserDialog(title="Επιλέξτε το αρχείο passwd προς εισαγωγή",
                                        action=Gtk.FileChooserAction.OPEN,
                                        buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                                 Gtk.STOCK_OK, Gtk.ResponseType.OK))

        chooser.set_icon_from_file('/usr/share/pixmaps/sch-scripts.svg')
        chooser.set_default_response(Gtk.ResponseType.OK)
        homepath = os.path.expanduser('~')
        chooser.set_current_folder(homepath)
        resp = chooser.run()
        if resp == Gtk.ResponseType.OK:
            passwd = chooser.get_filename()
            path = os.path.dirname(passwd)
            shadow = os.path.join(path, 'shadow')
            group = os.path.join(path, 'group')
            if not os.path.isfile(shadow):
                shadow = None
            if not os.path.isfile(group):
                group = None
            new_users = parsers.Passwd().parse(passwd, shadow, group)
            if len(new_users.users) == 0:
                text = "Το αρχείο '%s' δεν περιέχει δεδομένα." % passwd
                dialogs.ErrorDialog(text, "Σφάλμα").showup()
                return False
            chooser.destroy()
            import_dialog.ImportDialog(new_users)
        else:
            chooser.destroy()

    @classmethod
    def on_mi_import_csv_activate(cls, _widget):
        """Import csv file.

        If the file is empty return false.
        """
        chooser = Gtk.FileChooserDialog(title="Επιλέξτε το αρχείο CSV προς εισαγωγή",
                                        action=Gtk.FileChooserAction.OPEN,
                                        buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                                 Gtk.STOCK_OK, Gtk.ResponseType.OK))

        chooser.set_icon_from_file('/usr/share/pixmaps/sch-scripts.svg')
        chooser.set_default_response(Gtk.ResponseType.OK)
        homepath = os.path.expanduser('~')
        chooser.set_current_folder(homepath)
        resp = chooser.run()
        if resp == Gtk.ResponseType.OK:
            fname = chooser.get_filename()
            new_users = parsers.CSV().parse(fname)
            if len(new_users.users) == 0:
                text = "Το αρχείο '%s' δεν περιέχει δεδομένα." % fname
                dialogs.ErrorDialog(text, "Σφάλμα").showup()
                return False
            chooser.destroy()
            import_dialog.ImportDialog(new_users)
        else:
            chooser.destroy()

    def on_mi_export_csv_activate(self, _widget):
        """Export csv file."""
        users = self.get_selected_users()
        if len(users) == 0:
            if self.show_system_groups:
                users = self.system.users.values()
            else:
                users = [u for u in self.system.users.values() if not u.is_system_user()]
        export_dialog.ExportDialog(self.system, users)

## Server menu

    def on_mi_config_network_activate(self, _widget):
        ip_dialog.IpDialog(self.main_window)

    @classmethod
    def on_mi_ltsp_update_image_actv(cls, _widget):
        """Ltsp-update-image.

        Generates a compressed squashfs image from an LTSP chroot
        and exports it. Temporarily remove user accounts, logs,
        caches etc from the chroot before exporting the image.
        """
        message = "Θέλετε σίγουρα να προχωρήσετε στην δημοσίευση του εικονικού δίσκου;"
        second_message = "Ανάλογα με την ταχύτητα του επεξεργαστή σας και το μέγεθος του δίσκου σας, αυτή η διαδικασία μπορεί να χρειαστεί γύρω στα 10 λεπτά. Στη συνέχεια (επαν)εκκινήστε τους σταθμούς εργασίας."
        dlg = dialogs.AskDialog(message)
        dlg.format_secondary_text(second_message)
        response = dlg.showup()
        if response == Gtk.ResponseType.YES:
            subprocess.Popen(['./run-in-terminal', 'ltsp-update-image', '--cleanup', '/'])

    @classmethod
    def on_mi_ltsp_revert_image_actv(cls, _widget):
        """Swap chroot.img with chroot.img.old and update kernels."""
        message = "Θέλετε σίγουρα να προχωρήσετε στην επαναφορά του εικονικού δίσκου σε προηγούμενη έκδοση;"
        dlg = dialogs.AskDialog(message)
        response = dlg.showup()
        if response == Gtk.ResponseType.YES:
            subprocess.Popen(['./run-in-terminal', 'ltsp-update-image', '--revert', '/'])

    def on_mi_edit_lts_conf_activate(self, _widget):
        """Edit file lts.conf."""
        for file in glob.glob('/var/lib/tftpboot/ltsp/*/lts.conf'):
            self.edit_file(file)

    def on_mi_edit_pxelinux_cfg_actv(self, _widget):
        """Edit file pxelinux.cfg."""
        for file in glob.glob('/var/lib/tftpboot/ltsp/*/pxelinux.cfg/default'):
            self.edit_file(file)

    def on_mi_edit_shared_fldrs_actv(self, _widget):
        """Edit shared-folders."""
        self.edit_file('/etc/default/shared-folders')

    def on_mi_edit_dnsmasq_conf_actv(self, _widget):
        """Edit ltsp-server-dnsmasq.conf."""
        self.edit_file('/etc/dnsmasq.d/ltsp-server-dnsmasq.conf')

    def on_mi_purge_kernels_activate(self, _widget):
        maintenance.Purge(self.main_window)

    def on_mi_apt_get_clean_activate(self, _widget):
        maintenance.Clean(self.main_window)

    def on_mi_apt_get_purge_activate(self, _widget):
        maintenance.AutoRemove(self.main_window)

## View menu

    @classmethod
    def on_mi_view_column_toggled(cls, checkmenuitem, treeviewcolumn):
        treeviewcolumn.set_visible(checkmenuitem.get_active())

    def on_mi_show_syst_grps_toggled(self, _widget):
        self.show_system_groups = not self.show_system_groups
        self.groups_filter.refilter()
        self.users_filter.refilter()

    def on_mi_show_prvt_grps_toggled(self, _widget):
        self.show_private_groups = not self.show_private_groups
        self.groups_filter.refilter()

    def on_mi_refresh_activate(self, _widget):
        self.repopulate_treeviews()

## Users menu

    def on_mi_new_user_activate(self, _widget):
        """New user dialog activate."""
        user_form.NewUserDialog(self.system)

    def on_mi_edit_user_activate(self, _widget):
        """Edit user dialog activate."""
        user_form.EditUserDialog(self.system, self.get_selected_users()[0])

    def on_mi_delete_user_activate(self, _widget):
        """Delete users dialog activate."""
        users = self.get_selected_users()
        users_n = len(users)
        if users_n == 1:
            message = "Θέλετε σίγουρα να διαγράψετε τον χρήστη %s;" % users[0].name
            homes_message = "Να διαγραφεί και ο αρχικός κατάλογος του παραπάνω χρήστη."
            homes_warn = "ΠΡΟΣΟΧΗ: Αν ενεργοποιήσετε αυτήν την επιλογή θα διαγραφεί ο αρχικός κατάλογος του χρήστη, καθώς και όλα τα αρχεία που αυτός περιέχει, αλλά και ο αντίστοιχος κατάλογος e-mail στο /var/mail (εάν υπάρχει)."
        else:
            message = "Θέλετε σίγουρα να διαγράψετε τους παρακάτω %d χρήστες;" % users_n
            message += "\n" + ', '.join([user.name for user in users])
            homes_message = "Να διαγραφούν και οι αρχικοί κατάλογοι των παραπάνω χρηστών."
            homes_warn = "ΠΡΟΣΟΧΗ: Αν ενεργοποιήσετε αυτήν την επιλογή θα διαγραφούν οι αρχικοί κατάλογοι όλων των παραπάνω χρηστών, καθώς και όλα τα αρχεία που αυτοί περιέχουν, αλλά και οι αντίστοιχοι κατάλογοι e-mail στο /var/mail (εάν υπάρχουν)."
        homes_warn += "\n\nΗ ενέργεια αυτή είναι μη-αναστρέψιμη."

        dlg = dialogs.AskDialog(message)
        vbox = dlg.get_message_area()
        rm_homes_check = Gtk.CheckButton(homes_message)
        rm_homes_check.get_child().set_tooltip_text(homes_warn)
        rm_homes_check.show()
        vbox.pack_start(rm_homes_check, False, False, 12)
        response = dlg.showup()
        if response == Gtk.ResponseType.YES:
            rm_homes = rm_homes_check.get_active()
            for user in self.get_selected_users():
                self.system.delete_user(user, rm_homes)

    def on_mi_remove_user_activate(self, _widget):
        """Remove users from groups dialog."""
        users = self.get_selected_users()
        groups = self.get_selected_groups()
        users_n = len(users)
        group_names = ', '.join([group.name for group in groups])
        if users_n == 1:
            message = "Θέλετε σίγουρα να αφαιρέσετε τον χρήστη %s από τις επιλεγμένες ομάδες (%s);" % (users[0].name, group_names)
        else:
            message = "Θέλετε σίγουρα να αφαιρέσετε τους παρακάτω %d χρήστες από τις επιλεγμένες ομάδες (%s);" % (users_n, group_names)
            message += "\n" + ', '.join([user.name for user in users])

        response = dialogs.AskDialog(message).showup()
        if response == Gtk.ResponseType.YES:
            for user in self.get_selected_users():
                self.system.remove_user_from_groups(user, groups)

## Groups menu

    def on_mi_new_group_activate(self, _widget):
        """New group dialog activate."""
        group_form.NewGroupDialog(self.system, self.shared_fold)

    def on_mi_edit_group_activate(self, _widget):
        """Edit group dialog activate."""
        group_form.EditGroupDialog(self.system, self.shared_fold, self.get_selected_groups()[0])

    def on_mi_delete_group_activate(self, _widget):
        """Delete groups dialog activate."""
        groups = self.get_selected_groups()
        groups_n = len(groups)
        if groups_n == 1:
            message = "Θέλετε σίγουρα να διαγράψετε την ομάδα %s;" % groups[0].name
        else:
            message = "Θέλετε σίγουρα να διαγράψετε τις παρακάτω %d ομάδες;" % groups_n
            message += "\n" + ', '.join([group.name for group in groups])

        response = dialogs.AskDialog(message).showup()
        if response == Gtk.ResponseType.YES:
            self.shared_fold.remove(groups)
            for group in groups:
                self.system.delete_group(group)

## Help menu

    def on_mi_home_activate(self, _widget):
        """If help is needed, opens a link."""
        self.open_link('http://ts.sch.gr/wiki/Linux/LTSP')

    def on_mi_report_bug_activate(self, _widget):
        """If there is a bug to be reported, opens a link."""
        self.open_link('https://bugs.launchpad.net/sch-scripts')

    def on_mi_ask_question_activate(self, _widget):
        """If there is a question for sch-scripts, opens a link."""
        self.open_link('https://answers.launchpad.net/sch-scripts')

    def on_helpdesk_ticket_activate(self, _widget):
        self.open_link('http://helpdesk.sch.gr/ticketnew_user.php?category_id=9017')

    def on_mi_irc_activate(self, _widget):
        host = socket.gethostname()
        user = getpass.getuser()
        if user == "root":
            try:
                user = os.getlogin()
            except:
                user = os.getenv("SUDO_USER")
        lang = locale.getdefaultlocale()[0]
        self.open_link("http://ts.sch.gr/repo/irc?user=%s&host=%s&lang=%s" % \
                       (user, host, lang))

    def on_mi_forum_activate(self, _widget):
        """For more information in a forum, opens a link."""
        self.open_link('http://alkisg.mysch.gr/steki/index.php?board=67.0')

    def on_mi_map_activate(self, _widget):
        """For more information in who uses Ubuntu LTSP, opens a link."""
        self.open_link('http://ts.sch.gr/wiki/Linux/LTSP/Προχωρημένα/Χάρτης')

    def on_mi_lts_conf_manpage_activate(self, _widget):
        self.open_link('http://manpages.ubuntu.com/lts.conf')

    def on_mi_ltsp_info_activate(self, _widget):
        ltsp_info.LtspInfo(self.main_window)

    def on_mi_about_activate(self, _widget):
        about_dialog.AboutDialog(self.main_window)


# To export a man page:
# help2man -L el -s 8 -o sch-scripts.8 -N ./sch-scripts && man ./sch-scripts.8
def usage():
    """Print sch-scripts usage info."""
    print("""Χρήση: sch-scripts [ΕΠΙΛΟΓΕΣ]

Παρέχει ένα σύνολο εξαρτήσεων για την αυτοματοποίηση της εγκατάστασης
σχολικών εργαστηρίων και ένα γραφικό περιβάλλον που υποστηρίζει διαχείριση
λογαριασμών χρηστών, δημιουργία εικονικού δίσκου LTSP κ.α.

Πολλά από τα συμπεριλαμβανόμενα βοηθήματα προσανατολίζονται σε LTSP
εγκαταστάσεις, αλλά το πακέτο είναι χρήσιμο και χωρίς LTSP.

Περισσότερες πληροφορίες: http://ts.sch.gr/wiki/Linux/LTSP.

Επιλογές:
    -h, --help     Σελίδα βοήθειας της εφαρμογής.
    -v, --version  Προβολή έκδοσης των sch-scripts.

Αναφορά σφαλμάτων στο https://bugs.launchpad.net/sch-scripts.""")


def print_version():
    """Print sch-scripts version and copyright info."""
    print("""sch-scripts %s
Copyright (C) 2009-2018 Άλκης Γεωργόπουλος <alkisg@gmail.com>, Φώτης Τσάμης <ftsamis@gmail.com>.
Άδεια χρήσης GPLv3+: GNU GPL έκδοσης 3 ή νεότερη <http://gnu.org/licenses/gpl.html>.

Συγγραφή: by Άλκης Γεωργόπουλος <alkisg@gmail.com>, Φώτης Τσάμης <ftsamis@gmail.com>.""" % version.__version__)

if __name__ == '__main__':
    if len(sys.argv) == 2 and (sys.argv[1] == '-v' or sys.argv[1] == '--version'):
        print_version()
        sys.exit(0)
    elif len(sys.argv) == 2 and (sys.argv[1] == '-h' or sys.argv[1] == '--help'):
        usage()
        sys.exit(0)
    elif len(sys.argv) >= 2:
        usage()
        sys.exit(1)
    Gui()
    reactor.run()
