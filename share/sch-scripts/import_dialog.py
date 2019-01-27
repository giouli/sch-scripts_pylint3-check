#!/usr/bin/env python3
# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Import users dialog."""

import os
import re
import sys
import gi
from gi.repository import Gtk, Gdk

import common
import dialogs
import libuser
import user_form
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')


# NOTE: User.plainpw overrides the User.password if it's set
class ImportDialog:
    """Import users dialog."""

    def __init__(self, new_set):
        self.set = new_set
        # Remove the system users from the set
        for usr in list(self.set.users.values()):
            if usr.uid is not None and usr.is_system_user():
                self.set.remove_user(usr)

        gladefile = "import_dialog.ui"
        self.builder = Gtk.Builder()
        self.builder.add_from_file(gladefile)
        self.dialog = self.builder.get_object('import_dialog')

        dic = {"on_dialog_destroy" : self.exit,
               "on_apply" : self.apply,
               "on_auto_resolve" : self.resolve_conflicts,
               "on_delete_users_activate" : self.on_delete_users_activate,
               "on_cancel" : self.cancel}

        self.builder.connect_signals(dic)

        self.tree = self.builder.get_object("users_tree")
        self.apply = self.builder.get_object("apply_button")
        self.resolve = self.builder.get_object("resolve_button")
        self.menu = self.builder.get_object("menu")

        self.states = {'ok' : Gtk.STOCK_OK, 'error' : Gtk.STOCK_DIALOG_WARNING}
        self.dialog.show_all()
        self.tree_view()
        self.fill_tree(self.set)

    def tree_view(self):
        """Make the liststore.

        The first 20 cells refers to users values,
        the second 20 cells refers to color foreach of first 20 cells, the
        third 20 cells refers to conflicts and the last cell refers to first
        column image.
        """
        types = [str, int, int, str, str, str, str, str, str, str, str, str,
                 int, int, int, int, int, int, str, str]
        types.extend([str]*41)

        self.list = Gtk.ListStore(*types)
        self.tree.set_model(self.list)

        self.tree.connect("button_press_event", self.click)
        self.tree.connect("key_press_event", self.delete)
        self.tree.set_has_tooltip(True)
        self.tree.connect("query-tooltip", self.tooltip)
        self.tree.set_rubber_banding(True)

        # Make the columns in the preview treeview
        # First of all append the icon
        col_pixbuf = Gtk.TreeViewColumn("Κατάσταση", Gtk.CellRendererPixbuf(), stock_id=60)
        col_pixbuf.set_resizable(True)
        col_pixbuf.set_sort_column_id(60)
        self.tree.append_column(col_pixbuf)

        for (counter, header) in enumerate(libuser.CSV_USER_FIELDS):
            text_rend = Gtk.CellRendererText()
            text_rend.connect("edited", self.edited_text, self.list, counter)
            col = Gtk.TreeViewColumn(header, text_rend, text=counter,
                                     foreground=counter+20, editable=True)
            col.set_resizable(True)
            col.set_sort_column_id(counter)
            self.tree.append_column(col)
        self.tree.get_column(19).set_visible(False)

    def fill_tree(self, new_set):
        """Fill the preview popup dialog with new users."""
        for usr in new_set.users.values():
            self.auto_complete(usr)
            data = [usr.name, usr.uid, usr.gid, usr.primary_group, usr.rname, usr.office,
                    usr.wphone, usr.hphone, usr.other, usr.directory, usr.shell,
                    ",".join(usr.groups), usr.lstchg, usr.min, usr.max, usr.warn,
                    usr.inact, usr.expire, usr.password, usr.plainpw]
            # Fill the cells with default values
            for _i in range(20):
                data.append("black") # cell's foreground color
            for _i in range(20):
                data.append('') # cell's problem or ''
            data.append(self.states['ok']) # row's status
            row = self.list[self.list.append(data)]
            self.set_row_from_object(row)
        self.detect_conflicts()
        self.check_identical_users()

    def set_row_from_object(self, row):
        """Fill in the row with given data."""
        usr = self.set.users[row[0]]
        data = [usr.name, usr.uid, usr.gid, usr.primary_group, usr.rname, usr.office,
                usr.wphone, usr.hphone, usr.other, usr.directory, usr.shell,
                ",".join(usr.groups), usr.lstchg, usr.min, usr.max, usr.warn,
                usr.inact, usr.expire, usr.password, usr.plainpw]
        for i in range(len(data)):
            row[i] = data[i]

    def check_identical_users(self, other=libuser.system):
        """Check identical users.

        If there are users in the list that are identical to 
        a user in the system and ask for removal.
        """
        attrs = ['name', 'uid', 'gid', 'primary_group', 'rname', 'office',
                 'wphone', 'hphone', 'other', 'directory', 'shell', 'min',
                 'max', 'warn', 'inact', 'expire', 'password']

        identical = []
        for row in self.list:
            name = row[0]
            u_new = self.set.users[name]
            if name in other.users:
                u_old = other.users[name]
                same = True
                for attr in attrs:
                    if u_new.__dict__[attr] != u_old.__dict__[attr]:
                        same = False
                        break
                if set(u_new.groups+[u_new.primary_group]) != set(u_old.groups):
                    same = False
                if same:
                    identical.append(row.iter)
        if not identical:
            return
        msg = "Βρέθηκαν στο σύστημα οι ακόλουθοι %s χρήστες αυτής της λίστας με τα ίδια ακριβώς πεδία.\n\n"
        msg += "%s\n\n"
        msg += "Επιθυμείτε να διαγραφούν από αυτή τη λίστα οι πανομοιότυποι χρήστες και να μη γίνει εισαγωγή τους;"
        msg = msg % (len(identical), ', '.join(self.list[iter_][0] for iter_ in identical))
        resp = dialogs.AskDialog(msg, "Βρέθηκαν πανομοιότυποι χρήστες").showup()
        if resp == Gtk.ResponseType.YES:
            for iter_ in identical:
                self.remove_row(iter_)
            self.detect_conflicts()


    def auto_complete(self, user): # TODO: Maybe move me to libuser?
        """Fill the missing information of user, where possible."""
        #TODO: Complete the username from real name, this can't be done now
        # since we are using a dict to store users with username as a key
        #  - Needs design change -

        if user.directory in [None, '']:
            user.directory = os.path.join(libuser.HOME_PREFIX, user.name)
        if user.uid in [None, '']:
            set_uids = [user.uid for usr in self.set.users.values()]
            user.uid = libuser.system.get_free_uid(exclude=set_uids)

        set_gids = [usr.gid for usr in self.set.users.values()]
        sys_gids = {grp.gid : grp for grp in self.set.groups.values()}
        if user.gid in [None, '']:
            if user.primary_group in [None, '']:
                user.primary_group = user.name
            if user.name in libuser.system.groups:
                user.gid = libuser.system.groups[user.name].gid
            else:
                user.gid = libuser.system.get_free_gid(exclude=set_gids)
        else:
            if user.primary_group in [None, '']:
                if user.gid in sys_gids:
                    user.primary_group = sys_gids[user.gid].name
                else:
                    user.primary_group = user.name
        if user.primary_group in [None, '']:
            allgroups = self.set.groups.values()[:]
            allgroups.extend(libuser.system.groups.values())
            for gr_obj in allgroups:
                if gr_obj.gid == user.gid:
                    user.primary_group = gr_obj.name
                    break
        if user.shell in [None, '']:
            user.shell = '/bin/bash'
        if user.min in [None, '']:
            user.min = 0
        if user.max in [None, '']:
            user.max = 99999
        if user.warn in [None, '']:
            user.warn = 7
        if user.lstchg in [None, '']:
            user.lstchg = common.days_since_epoch()
        if user.inact in [None, '']:
            user.inact = -1
        if user.expire in [None, '']:
            user.expire = -1
        if user.password in [None, '']:
            user.password = '!'
        if user.plainpw is None:
            user.plainpw = ''

    def set_row_props(self, row, col, prob, color=None, state=None):
        """Set how the rows will appear."""
        row[col+40] = prob
        if color:
            row[col+20] = color
        else:
            if prob == '':
                row[col+20] = 'black'
            else:
                row[col+20] = 'red'
        if state:
            row[60] = self.states[state]
        else:
            if prob == '':
                other = False
                for i in range(20, 40): # Check if there are other problems to set the proper icon
                    if row[i] == 'red':
                        other = True
                        break
                if other:
                    row[60] = self.states['error']
                else:
                    row[60] = self.states['ok']
            else:
                row[60] = self.states['error']

    def detect_conflicts(self):
        """Detect conflicts.

        Detects and marks the conflicts in the treeview based on the user
        object.
        Here we don't check for conflicts with secondary groups as they are
        easily resolvable.
        """
        # All the system users
        sys_users = {'uids' : [], 'gids' : [], 'dirs' : []}
        sys_users['uids'] = [user.uid for user in libuser.system.users.values()]
        sys_users['gids'] = [user.gid for user in libuser.system.users.values()]
        sys_users['dirs'] = [user.directory for user in libuser.system.users.values()]
        # All the users in the new Set
        new_users = {'uids' : [], 'gids' : [], 'dirs' : []}
        new_users['uids'] = [user.uid for user in self.set.users.values()]
        new_users['gids'] = [user.gid for user in self.set.users.values()]
        new_users['dirs'] = [user.directory for user in self.set.users.values()]

        passed_users = {'names' : [], 'uids' : [], 'gids' : [], 'dirs' : []}
        errors_found = False
        for row in self.list:
            usr = self.set.users[row[0]]
            # Clear the currently marked conflicts, if any
            for cell in range(0, 20):
                self.set_row_props(row, cell, '')

            # FIXME: Possibly not an issue, but problems with system users
            # will override problems with new users.
            # Illegal input problems will *not* be overriden.

            # 'char' : Illegal inputted characters/regexp mismatch
            # 'dup' : duplicate (only about the new users)
            # 'con' : conflict (like duplicate but for existing/system users)
            # 'hijack' : special case where the home exists, is not used by a
            #            system user, but its uid:gid pair is different from the
            #            new user's one.


            # Illegal input checking #FIXME: This should be in a separate function
                                     #and (for later): executed only once, since
                                     #the edit dialog won't allow illegal input
            def invalidate(numb):
                """Check the validity of the attributes of a user and if there are any conflicts."""
                self.set_row_props(row, numb, 'char')
            if not libuser.system.name_is_valid(usr.name):
                invalidate(0)
            if not libuser.system.uid_is_valid(usr.uid):
                invalidate(1)
            if not libuser.system.gid_is_valid(usr.gid):
                invalidate(2)
            if not libuser.system.name_is_valid(usr.primary_group):
                invalidate(3)
            if not libuser.system.gecos_is_valid(usr.rname):
                invalidate(4)
            if not libuser.system.gecos_is_valid(usr.office):
                invalidate(5)
            if not libuser.system.gecos_is_valid(usr.wphone):
                invalidate(6)
            if not libuser.system.gecos_is_valid(usr.hphone):
                invalidate(7)
            if not libuser.system.gecos_is_valid(usr.other):
                invalidate(8)
            # Not checking homedir validity
            if not libuser.system.shell_is_valid(usr.shell):
                invalidate(10)
            for group in usr.groups:
                if not libuser.system.name_is_valid(group):
                    invalidate(11)
                    break
            chage = [usr.lstchg, usr.min, usr.max, usr.warn, usr.inact, usr.expire]
            for numb, attr in enumerate(chage, 12):
                if attr > 2147483647 or attr < -1:
                    invalidate(numb)

            # Duplicate checking (New users)
            if usr.name in passed_users['names']:
                self.set_row_props(row, 0, 'dup')
            if usr.uid in passed_users['uids']:
                self.set_row_props(row, 1, 'dup')
            #if usr.gid in passed_users['gids']:
            # We don't care for > 1 users having the same primary group
            #    self.set_row_props(row, 2, 'dup')
            if usr.directory in passed_users['dirs']:
                self.set_row_props(row, 9, 'dup')

            # Conflict checking (Existing system users)
            if usr.name in libuser.system.users:
                self.set_row_props(row, 0, 'con')
            if usr.uid in sys_users['uids']:
                self.set_row_props(row, 1, 'con')
            # Check if the given GID belongs to the given group name
            if usr.primary_group in libuser.system.groups:
                should_be = libuser.system.groups[usr.primary_group].gid
                if usr.gid != should_be:
                    self.set_row_props(row, 2, 'mismatch %s' % should_be)
            else:
                if usr.gid in sys_users['gids']:
                    should_be = None
                    for grp in libuser.system.groups.values():
                        if usr.gid == grp.gid:
                            should_be = grp.name
                            break
                    if should_be != usr.primary_group:
                        self.set_row_props(row, 3, 'mismatch %s' % should_be)
            #if usr.gid in sys_users['gids']:
            # We don't care for > 1 users having the same primary group
            #    self.set_row_props(row, 2, 'con')
            if usr.directory in sys_users['dirs']:
                self.set_row_props(row, 9, 'con')
            else:
                # Special case, we want to use existing home dirs if they are not already used.
                if os.path.isdir(usr.directory) and usr.directory not in sys_users['dirs']:
                    # See if the home and the uid:gid of the user are different
                    #print "Homedir for user %s exists in the FS." % usr.name # XXX: Debug
                    dir_stat = os.stat(usr.directory)
                    if usr.uid != int(dir_stat.st_uid):
                        self.set_row_props(row, 1, 'hijack')
                        self.set_row_props(row, 9, 'hijack')
                    if usr.gid != dir_stat.st_gid:
                        self.set_row_props(row, 2, 'hijack')
                        self.set_row_props(row, 9, 'hijack')
                    #print "\tUser: - %s:%s -" % (usr.uid, usr.gid) # XXX: Debug
                    #print "\tDir : - %s:%s -" % (dir_stat.st_uid, dir_stat.st_gid) # XXX: Debug

            passed_users['names'].append(usr.name)
            passed_users['uids'].append(usr.uid)
            passed_users['gids'].append(usr.gid)
            passed_users['dirs'].append(usr.directory)

            if row[60] == self.states['error']:
                errors_found = True

        self.apply.set_sensitive(not errors_found)

    def resolve_conflicts(self, _widget=None):
        """If there are any conflicts found they are resolved."""
        # All the system users
        sys_users = {'uids' : [], 'gids' : [], 'dirs' : []}
        sys_users['uids'] = [user.uid for user in libuser.system.users.values()]
        sys_users['gids'] = [user.gid for user in libuser.system.users.values()]
        sys_users['dirs'] = [user.directory for user in libuser.system.users.values()]
        # All the users in the new Set
        new_users = {'uids' : [], 'gids' : [], 'dirs' : []}
        new_users['uids'] = [user.uid for user in self.set.users.values()]
        new_users['gids'] = [user.gid for user in self.set.users.values()]
        new_users['dirs'] = [user.directory for user in self.set.users.values()]

        log = []
        def log_msg(item, user, attr1, attr2):
            """Show a message with the change applied on a user."""
            txt = "Αλλάχθηκε το %s του χρήστη '%s' από %s σε %s." % (item, user, attr1, attr2)
            log.append(txt)
            return txt
        def log_uid(usr, field1, field2):
            return log_msg('UID', usr, field1, field2)
        def log_gid(usr, field1, field2):
            return log_msg('GID', usr, field1, field2)
        def _log_home(usr, field1, field2):
            return log_msg('Home', usr, field1, field2)
        def log_group(usr, field1, field2):
            return log_msg('όνομα του primary group', usr, field1, field2)

        for row in self.list:
            if row[60] != self.states['error']:
                continue
            usr = self.set.users[row[0]]
            ofs = 40

            if row[1+ofs] in ['dup', 'con']:
                new_uid = libuser.system.get_free_uid(exclude=new_users['uids'])
                new_users['uids'].append(new_uid)
                log_uid(usr.name, usr.uid, new_uid)
                usr.uid = new_uid
                self.set_row_props(row, 1, '')

            elif row[1+ofs] == 'hijack':
                dir_uid = os.stat(usr.directory).st_uid
                new_users['uids'].append(dir_uid)
                log_uid(usr.name, usr.uid, dir_uid)
                usr.uid = dir_uid
                self.set_row_props(row, 1, '')

            #if row[2+ofs] in ['dup', 'con']:
            #    new_gid = libuser.system.get_free_gid(exclude=new_users['gids'])
            #    new_users['gids'].append(new_gid)
            #    log_gid(usr.name, usr.gid, new_gid)
            #    usr.uid = new_uid
            #    self.set_row_props(row, 2, '')

            if 'mismatch' in row[2+ofs]:
                new_gid = int(row[2+ofs].split()[1])
                new_users['gids'].append(new_gid)
                log_gid(usr.name, usr.gid, new_gid)
                if usr.primary_group in self.set.groups:
                    self.set.groups[usr.primary_group].gid = new_gid
                usr.gid = new_gid
                self.set_row_props(row, 2, '')

            if row[2+ofs] == 'hijack':
                dir_gid = os.stat(usr.directory).st_gid
                new_users['gids'].append(dir_gid)
                log_gid(usr.name, usr.gid, dir_gid)
                usr.gid = dir_gid
                self.set_row_props(row, 2, '')

            if 'mismatch' in row[3+ofs]:
                new_gname = row[3+ofs].split()[1]
                log_group(usr.name, usr.primary_group, new_gname)
                if new_gname in self.set.groups:
                    if usr.name not in self.set.groups[new_gname].members:
                        self.set.groups[new_gname].members[usr.name] = usr
                else:
                    self.set.groups[new_gname] = libuser.Group(new_gname, usr.gid)
                    self.set.groups[new_gname].members[usr.name] = usr
                if usr.primary_group in self.set.groups:
                    if self.set.groups[usr.primary_group].members.keys() == [usr.name]:
                        del self.set.groups[usr.primary_group]
                    else:
                        del self.set.groups[usr.primary_group].members[usr.name]
                usr.primary_group = new_gname
                self.set_row_props(row, 3, '')
            self.set_row_from_object(row)

        num = len(log)
        if num > 0:
            log_dlg = self.builder.get_object('log_dialog')
            buf = self.builder.get_object('logbuffer')
            buf.set_text('\n'.join(log))
            log_dlg.run()
            log_dlg.hide()
            self.detect_conflicts()
        else:
            dialogs.WarningDialog('Δεν ήταν δυνατή η αυτόματη επίλυση κάποιου προβλήματος').showup()

    def edit(self, _widget, user):
        """Open a dialog to edit user."""
        form = user_form.ReviewUserDialog(libuser.system, user, role='')
        form.dialog.set_transient_for(self.dialog)
        form.dialog.set_modal(True)

    def apply(self, _widget):
        """Apply the changes in order to create a new group and add users in it."""
        text = "Να δημιουργηθούν οι νέοι χρήστες;"
        response = dialogs.AskDialog(text, "Confirm").showup()
        if response == Gtk.ResponseType.YES:
            new_groups = {}
            new_gids = [usr.gid for usr in self.set.users.values()]
            sys_gids = [grp.gid for grp in libuser.system.groups.values()]
            for usr in self.set.users.values():
                if usr.primary_group not in libuser.system.groups:
                    if usr.primary_group not in new_groups:
                        g_obj = libuser.Group(usr.primary_group, usr.gid)
                        new_groups[usr.primary_group] = g_obj
                    new_groups[usr.primary_group].members[usr.name] = usr

            for usr in self.set.users.values():
                for grp in usr.groups:
                    if grp not in libuser.system.groups:
                        if grp not in new_groups:
                            g_obj = libuser.Group(grp)
                            if grp in self.set.groups:
                                g_obj.gid = self.set.groups[grp].gid
                            if g_obj.gid in new_gids+sys_gids or g_obj.gid is None:
                                g_obj.gid = libuser.system.get_free_gid(exclude=new_gids)
                                new_gids.append(g_obj.gid)
                            new_groups[grp] = g_obj
                        new_groups[grp].members[usr.name] = usr

            for group in new_groups.values():
                gr_tmp = libuser.Group(group.name, group.gid)
                libuser.system.add_group(gr_tmp)
            for usr in self.set.users.values():
                libuser.system.add_user(usr)
            for group in new_groups.values():
                for usr in group.members.values():
                    libuser.system.add_user_to_groups(usr, [group])

        else:
            return False

        self.dialog.destroy()


    def cancel(self, _widget):
        """Cancle the procedure and closes the dialog."""
        self.dialog.destroy()

    def exit(self, _widget, _event):
        """Exit the procedure and closes the dialog."""
        self.dialog.destroy()

    def tooltip(self, _widget, attr1, attr2, keyboard_tip, tooltip):
        """Show the error messages in each case in a form of a tooltip."""
        if not _widget.get_tooltip_context(attr1, attr2, keyboard_tip):
            return False
        else:
            _keyboard_mode, cellx, celly, model, path, _iter = _widget.get_tooltip_context(attr1, attr2, keyboard_tip)
            row_info = _widget.get_path_at_pos(int(cellx), int(celly))
            if row_info is not None:
                col = row_info[1]

                if model[path][0+40] == "con" and col.get_title() == "Όνομα χρήστη":
                    tooltip.set_text("Αυτό το όνομα χρήστη υπάρχει ήδη στο σύστημα")
                elif model[path][0+40] == "char" and col.get_title() == "Όνομα χρήστη":
                    tooltip.set_text("Αυτό το όνομα χρήστη δεν είναι αποδεκτό")
                elif model[path][1+40] == "con" and col.get_title() == "UID":
                    tooltip.set_text("Αυτό το UID υπάρχει ήδη στο σύστημα")
                elif model[path][1+40] == "dup" and col.get_title() == "UID":
                    tooltip.set_text("Αυτό το UID υπάρχει ήδη σε αυτή τη λίστα")
                elif model[path][1+40] == "hijack" and col.get_title() == "UID":
                    tooltip.set_text("Αυτό το UID είναι διαφορετικό από αυτό του home καταλόγου που δώσατε")
                elif model[path][2+40] == "hijack" and col.get_title() == "UID":
                    tooltip.set_text("Αυτό το GID είναι διαφορετικό από αυτό του home καταλόγου που δώσατε")
                elif model[path][9+40] == "con" and col.get_title() == "Κατάλογος":
                    tooltip.set_text("Αυτός ο κατάλογος χρησιμοποιείται από κάποιον άλλο χρήστη του συστήματος")
                elif model[path][9+40] == "dup" and col.get_title() == "Κατάλογος":
                    tooltip.set_text("Αυτός ο κατάλογος χρησιμοποιείται από κάποιον άλλο χρήστη σε αυτή τη λίστα")
                elif model[path][9+40] == "hijack" and col.get_title() == "Κατάλογος":
                    tooltip.set_text("Αυτός ο κατάλογος υπάρχει στο σύστημα αλλά με διαφορετικά UID ή/και GID από αυτά που δώσατε")
                elif 'mismatch' in model[path][2+40] and col.get_title() == "Κύρια ομάδα":
                    tooltip.set_text("Αυτό το GID δεν ανήκει στην ομάδα %s" % model[path][3])
                elif 'mismatch' in model[path][3+40] and col.get_title() == "Όνομα κύριας ομάδας":
                    tooltip.set_text("Το GID αυτής της ομάδας δεν είναι %s" % model[path][2])
                else:
                    return

                _widget.set_tooltip_cell(tooltip, path, col, None)
                return True

    def click(self, treeview, _event):
        '''if _event.button == 1 and _event.type == Gdk.EventType._2BUTTON_PRESS:
            selection = treeview.get_selection()
            model, paths = selection.get_selected_rows()
            if len(paths) > 0:
                user = self.set.users[model[paths[0]][0]]
                self.Edit(None, user)''' # TODO: Uncomment me when the Dialog editing can be done
        if _event.button == 3 and _event.type == Gdk.EventType.BUTTON_PRESS:
            selection = treeview.get_selection()
            _model, paths = selection.get_selected_rows()
            if len(paths) > 0:
                self.menu.popup(None, None, None, None, _event.button, _event.time)
                return True

    def on_delete_users_activate(self, _widget):
        selection = self.tree.get_selection()
        model, paths = selection.get_selected_rows()
        iters = [model.get_iter(path) for path in paths]
        for i in iters:
            self.remove_row(i)
        self.detect_conflicts()

    def edited_text(self, _cell, path, new_text, model, col):
        """Set the attributes of a user."""
        username = model[path][0]
        usr = self.set.users[username]
        int_columns = [1, 2, 12, 13, 14, 15, 16, 17]
        attrs = ['name', 'uid', 'gid', 'primary_group', 'rname', 'office',
                 'wphone', 'hphone', 'other', 'directory', 'shell', 'groups',
                 'lstchg', 'min', 'max', 'warn', 'inact', 'expire', 'password',
                 'plainpw']
        if col in int_columns:
            try:
                usr.__dict__[attrs[col]] = int(new_text)
            except ValueError:
                return
        else:
            if col == 0:
                if new_text in self.set.users:
                    return
                usr.name = new_text
                usr.directory = '/home/%s' % new_text
                self.set.users[new_text] = self.set.users.pop(username)
                model[path][0] = usr.name
            elif col == 11:
                usr.groups = new_text.strip().split(',')
            elif col == 19:
                # Set user.password from plainpw
                usr.plainpw = new_text
                usr.password = libuser.system.encrypt(usr.plainpw)
            else:
                usr.__dict__[attrs[col]] = new_text
        self.set_row_from_object(model[path])
        self.detect_conflicts()

    def delete(self, treeview, _event):
        """Delete the selected rows."""
        if Gdk.keyval_name(_event.keyval) == "Delete":
            selection = treeview.get_selection()
            model, paths = selection.get_selected_rows()
            iters = [model.get_iter(path) for path in paths]
            for i in iters:
                self.remove_row(i)
            self.detect_conflicts()

    def remove_row(self, iter_):
        """Remove a row with a user."""
        username = self.list[iter_][0]
        self.list.remove(iter_)
        self.set.remove_user(self.set.users[username])

if __name__ == "__main__":
    INTERFACE = ImportDialog()
    Gtk.main()
