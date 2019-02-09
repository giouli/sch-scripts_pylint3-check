# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
"""New group form."""

import re
import os
import subprocess
from gi.repository import Gtk, Gdk
import libuser
import shared_folders

class GroupForm(object):
    """Creating a group.

    Show a form in order to create a new group.
    """

    def __init__(self, system, oneself):
        self.system = system
        self.oneself = oneself
        self.mode = None
        self.group = None
        self.builder = Gtk.Builder()
        self.builder.add_from_file('group_form.ui')

        self.dialog = self.builder.get_object('dialog')
        self.groupname = self.builder.get_object('name_entry')
        self.gid_entry = self.builder.get_object('gid_entry')
        self.users_tree = self.builder.get_object('users_treeview')
        self.users_store = self.builder.get_object('users_liststore')
        self.users_filter = self.builder.get_object('users_filter')
        self.users_sort = self.builder.get_object('users_sort')
        self.sys_group_check = self.builder.get_object('sys_group_check')
        self.gname_valid_icon = self.builder.get_object('groupname_valid')
        self.gid_valid_icon = self.builder.get_object('gid_valid')
        self.has_shared = self.builder.get_object('shared_folders_check')
        self.show_sys_users = False

        self.users_filter.set_visible_func(self.users_visible_func)
        self.users_sort.set_sort_column_id(2, Gtk.SortType.ASCENDING)

        # Fill the users (member selection) treeview
        for user, user_obj in system.users.items():
            if self.mode == 'edit' and user_obj.gid == self.group.gid:
                activatable = False
            else:
                activatable = True
            self.users_store.append([user_obj, False, user, activatable])

    def on_show_sys_users_toggled(self, _widget):
        """Show the system users."""
        self.show_sys_users = not self.show_sys_users
        self.users_filter.refilter()

    def users_visible_func(self, model, itr, _x):
        """Return true or false for system users.

        If the option Show system users is on, it retuns true
        and shows all the users, else it returns false
        and system users don't appear in the user's list.
        """
        system_user = model[itr][0].is_system_user()
        return self.show_sys_users or not system_user

    def on_name_entry_changed(self, _widget):
        """Edit the name entry for a group.

        Also check if the new entry is availabe and valid.
        """
        groupname = _widget.get_text()
        valid_name = self.system.name_is_valid(groupname)
        free_name = groupname not in self.system.groups
        if self.mode == 'edit':
            free_name = free_name or groupname == self.group.name

        if valid_name and free_name:
            icon = Gtk.STOCK_OK
        else:
            icon = Gtk.STOCK_CANCEL
        self.gname_valid_icon.set_from_stock(icon, Gtk.IconSize.BUTTON)
        self.set_apply_sensitivity()

    def on_gid_changed(self, _widget):
        gid = _widget.get_text()
        try:
            gid = int(gid)
        except:
            self.gid_valid_icon.set_from_stock(Gtk.STOCK_CANCEL, Gtk.IconSize.BUTTON)
            self.set_apply_sensitivity()
            return

        if (self.mode == 'edit' and gid == self.group.gid) or self.system.gid_is_free(gid):
            icon = Gtk.STOCK_OK
        else:
            icon = Gtk.STOCK_CANCEL
        self.gid_valid_icon.set_from_stock(icon, Gtk.IconSize.BUTTON)
        self.set_apply_sensitivity()

    def on_user_toggled(self, _widget, path):
        path = self.users_sort[path].path
        path = self.users_sort.convert_path_to_child_path(path)
        path = self.users_filter.convert_path_to_child_path(path)

        self.users_store[path][1] = not self.users_store[path][1]

    def set_apply_sensitivity(self):
        sen = self.gid_valid_icon.get_stock()[0] == self.gname_valid_icon.get_stock()[0] == Gtk.STOCK_OK
        self.builder.get_object('apply_button').set_sensitive(sen)

    def on_dialog_delete_event(self, _widget, _event):
        """Close the dialog."""
        self.dialog.destroy()

    def on_cancel_clicked(self, _widget):
        """Cancel the dialog."""
        self.dialog.destroy()

class NewGroupDialog(GroupForm):
    """Open a dialog for a new group."""

    def __init__(self, system, oneself):
        self.mode = 'new'
        super(NewGroupDialog, self).__init__(system, oneself)
        self.builder.connect_signals(self)

        self.gid_entry.set_text(str(system.get_free_gid()))

        self.dialog.show()

    def on_apply_clicked(self, _widget):
        """Apply the changes for the new group, then close the dialog."""
        name = self.groupname.get_text()
        gid = int(self.gid_entry.get_text())
        members = {u[0].name : u[0] for u in self.users_store if u[1]}
        grp = libuser.Group(name, gid, members)
        self.system.add_group(grp)
        if self.has_shared.get_active():
            self.oneself.add([grp.name])
        self.dialog.destroy()

class EditGroupDialog(GroupForm):
    """Edit an existing group.

    Activate the members of the group and check if the shared folders are enabled.
    """

    def __init__(self, system, oneself, group):
        self.mode = 'edit'
        self.group = group
        super(EditGroupDialog, self).__init__(system, oneself)
        self.builder.connect_signals(self)

        self.groupname.set_text(group.name)
        self.gid_entry.set_text(str(group.gid))

        # Activate the members of the group
        for row in self.users_store:
            if row[0].name in self.group.members:
                row[1] = True

        # See if the group has shared folders enabled
        if group.name in self.oneself.list_shared():
            self.has_shared.set_active(True)
            self.shared_state = True
        else:
            self.shared_state = False

        self.has_shared.connect('toggled', self.on_has_shared_check_toggled)

        self.dialog.show()

    def on_has_shared_check_toggled(self, _widget):
        """Check if the shared folders are enabled and show a warning."""
        warn_label = self.builder.get_object('warning')
        if not self.has_shared.get_active() and self.shared_state:
            warn_label.show()
        else:
            warn_label.hide()

    def on_apply_clicked(self, _widget):
        """Apply the changes.

        Remove the users that are not members of the current group
        and apply the changes on the shared folders.
        """
        old_name = self.group.name
        old_gid = self.group.gid
        old_members = self.group.members
        self.group.name = self.groupname.get_text()
        self.group.gid = int(self.gid_entry.get_text())
        self.group.members = {u[0].name : u[0] for u in self.users_store if u[1]}

        self.system.edit_group(old_name, self.group)

        # Remove the group from users that are no more members of this group
        for user in old_members.values():
            if user not in self.group.members.values():
                self.system.remove_user_from_groups(user, [self.group])
        if self.shared_state and not self.has_shared.get_active():
            # Shared folders were active but now they are not
            self.oneself.remove([self.group.name])
        elif self.has_shared.get_active():
            if not self.shared_state:
                # Shared folders were not active and now they are
                self.oneself.add([self.group.name])
            else:
                # Share folders were and are active, check for name/gid changes
                if old_name != self.group.name:
                    self.oneself.rename(old_name, self.group.name)
                elif old_gid != self.group.gid:
                    self.oneself.mount([self.group.name])

        self.dialog.destroy()
