#!/usr/bin/env python3
# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
"""User handling classes and functions."""

import pwd
import os
import spwd
import grp
import operator
import subprocess
import re
import crypt
import random
from twisted.internet import inotify
from twisted.python import filepath
import common
import iso843



FIRST_SYSTEM_UID = 0
LAST_SYSTEM_UID = 999

FIRST_SYSTEM_GID = 0
LAST_SYSTEM_GID = 999

FIRST_UID = 1000
LAST_UID = 29999

FIRST_GID = 1000
LAST_GID = 29999
NAME_REGEX = "^[a-z][-a-z0-9_]*$"
HOME_PREFIX = "/home"

USER_FIELDS = ['Όνομα χρήστη', 'UID', 'Κύρια ομάδα', 'Ονοματεπώνυμο', 'Γραφείο',
               'Τηλ. γραφείου', 'Τηλ. οικίας', 'Άλλο', 'Κατάλογος', 'Κέλυφος', 'Ομάδες',
               'Τελευταία αλλαγή κωδικού', 'Ελάχιστη διάρκεια', 'Μέγιστη διάρκεια', 'Προειδοποίηση', 'Ανενεργός', 'Λήξη']

['Username', 'UID', 'GID', 'Primary Group Name', 'Real name', 'Office', 'Office phone', 'Home phone', 'Other', 'Directory', 'Shell', 'Groups', 'Last password change', 'Minimum days', 'Maximum days', 'Warn', 'Inactive', 'Expiration', 'Encrypted password', 'Password']
CSV_USER_FIELDS = USER_FIELDS[:]
CSV_USER_FIELDS.insert(3, 'Όνομα κύριας ομάδας')
CSV_USER_FIELDS.extend(['Κρυπτογραφημένος κωδικός', 'Κωδικός'])


class User:
    """Make the user's fields for the form."""

    def __init__(self, name=None, uid=None, gid=None, rname="", office="", wphone="",
                 hphone="", other="", directory=None, shell="/bin/bash", groups=None, lstchg=None,
                 min=0, max=99999, warn=7, inact=-1, expire=-1, password="*", plainpw=None):

        self.name, self.uid, self.gid, self.rname, self.office, self.wphone, self.hphone,\
        self.other, self.directory, self.shell, self.groups, self.lstchg, self.min, self.max, self.warn, \
        self.inact, self.expire, self.password, self.plainpw = name, uid, gid, rname, \
        office, wphone, hphone, other, directory, shell, groups, lstchg, min, max, warn, inact, \
        expire, password, plainpw

        if not self.name and self.rname:
            self.name = iso843.transcript(rname)

        if self.groups is None:
            self.groups = []

        if self.gid is not None:
            try:
                self.primary_group = grp.getgrgid(self.gid).gr_name
            except:
                self.primary_group = ''
        else:
            self.primary_group = None

    def __str__(self):
        return str(self.__dict__)

    def is_system_user(self):
        return not (self.uid >= FIRST_UID and self.uid <= LAST_UID)

    def get_ids_from_home(self, base='/home'):
        """Get ids.

        Return the owner's UID and GID of the /home/<username>
        if this exists or None.
        """
        path = os.path.join(base, self.name)
        if os.isdir(path):
            stat = os.stat(path)
            return [stat.st_uid, stat.st_gid]
        return None


class Group:
    """Make the group's fields for the form."""

    def __init__(self, name=None, gid=None, members=None, password=""):
        self.name, self.gid, self.members, self.password = \
            name, gid, members, password

        if self.members is None:
            self.members = {}

    def is_user_group(self):
        return self.gid >= FIRST_GID and self.gid <= LAST_GID

    def is_private(self):
        # A UPG has the same name as the user for which it was created
        # and that user is the only member of the UPG.
        return self.is_user_group() and self.name in self.members and len(self.members) == 1


# TODO: Change implementation, don't use dicts since they have to be updated
#       when the user/group_object.name changes. python sets would be good.
class Set(object):
    """A set of User and Group objects."""

    def __init__(self, users=None, groups=None):
        self.users = {} if users is None else users
        self.groups = {} if groups is None else groups

    def add_user(self, user):
        """Add a new User object in the Set."""
        if user.name in self.users:
            raise ValueError("User '%s' exists" % user.name)
        self.users[user.name] = user

    def remove_user(self, user):
        """Remove a User object from the Set.

        This will also remove the user from the Group objects and remove from
        the Set the private Group of this user, if he had one.
        """
        for group in user.groups:
            if group in self.groups:
                grup = self.groups[group]
                if grup.is_private() and grup.name == user.name:
                    del self.groups[grup.name]
                else:
                    del grup.members[user.name]
        del self.users[user.name]

    def add_group(self, group):
        """Add a new Group object in the Set.

        This will also:
        - Add the User objects which are members of this group to the Set.users
          in case they are not there already.
        - Update the User objects which are members of this group to include it
          in their User.groups lists.
        """
        if group.name in self.groups:
            raise ValueError("Group '%s' exists" % group.name)
        self.groups[group.name] = group

        for user_obj in group.members.values():
            if user_obj.name not in self.users:
                self.add_user(user_obj)
            if group.name not in user_obj.groups:
                user_obj.groups.append(group.name)

    def remove_group(self, group):
        """Remove a Group object from the Set.

        This will also remove the group from the User objects and remove from
        the Set all the Users which have this group as primary.
        """
        for user_obj in self.users.values():
            if group.name in user_obj.groups:
                if len(user_obj.groups) == 1:
                    del self.users[user_obj.name]
                else:
                    user_obj.groups.remove(group.name)
        del self.groups[group.name]

    def uid_is_free(self, uid):
        return uid not in [user.uid for user in self.users.values()]

    def gid_is_free(self, gid):
        return gid not in [group.gid for group in self.groups.values()]

    def get_free_uid(self, start=FIRST_UID, end=LAST_UID, reverse=False, ignore=None, exclude=None):
        """Find and return a free user id."""
        used_uids = [user.uid for user in self.users.values()]
        if exclude is not None:
            used_uids.extend(exclude)
        val = range(start, end+1)
        if reverse:
            val = reversed(val)

        uid = None

        for i in val:
            if i == ignore or i not in used_uids:
                uid = i
                break
        return uid

    def get_free_gid(self, start=FIRST_UID, end=LAST_UID, reverse=False, ignore=None, exclude=None):
        """Find and return a free group id."""
        used_gids = [group.gid for group in self.groups.values()]
        if exclude is not None:
            used_gids.extend(exclude)
        val = range(start, end+1)
        if reverse:
            val = reversed(val)

        gid = None

        for i in val:
            if i == ignore or i not in used_gids:
                gid = i
                break
        return gid


class Event:
    def __init__(self):
        self.subscribers = []

    def connect(self, func):
        self.subscribers.append(func)

    def notify(self, arg=None, *_kwargs):
        for subscriber in self.subscribers:
            subscriber(arg)


class System(Set):
    """Command for system modifications."""

    def __init__(self):
        super(System, self).__init__()
        self.load()
        # These might be updated from shared_folders, if they're used
        self.teachers = 'teachers'
        self.share_groups = [self.teachers]

        # INotifier for /etc/group and /etc/shadow
        self.system_event = Event()
        self.libuser_event = Event()
        self.system_event.connect(self.on_system_changed)
        self.mask = inotify.IN_MODIFY
        self.group_fp = filepath.FilePath('/etc/group')
        self.shadow_fp = filepath.FilePath('/etc/shadow')
        self.notifier = inotify.INotify()
        self.notifier.startReading()
        self.notifier._addWatch(self.group_fp, self.mask, False, [self.on_fd_changed])
        self.notifier._addWatch(self.shadow_fp, self.mask, False, [self.on_fd_changed])

    def add_group(self, group):
        common.run_command(['groupadd', '-g', str(group.gid), group.name])
        for user in group.members.values():
            if user in self.users.values():
                common.run_command(['usermod', '-a', '-G', group.name, user.name])
            else:
                self.add_user(user)

    @classmethod
    def edit_group(cls, groupname, group):
        """Edit a group."""
        common.run_command(['groupmod', '-g', str(group.gid), '-n', group.name, groupname])
        for user in group.members.values():
            common.run_command(['usermod', '-a', '-G', group.name, user.name])

    @classmethod
    def delete_group(cls, group):
        common.run_command(['groupdel', group.name])

    def add_user(self, user, create_home=True):
        """Add a new user."""
        cmd = ["useradd"]
        if create_home:
            cmd.extend(['-m', '-d', user.directory])
        cmd.extend(['-g', str(user.gid)])
        cmd.append(user.name)
        common.run_command(cmd)
        self.update_user(user.name, user)

    @classmethod
    def _strcnv(cls, val):
        return [str(i) for i in val]

    def update_user(self, username, user):
        """Update the main values of a user."""
        cmd = ['usermod']
        cmd.extend(['-d', user.directory])
        cmd.extend(['-g', user.gid])
        cmd.extend(['-G', ','.join(user.groups)])
        cmd.extend(['-l', user.name])
        if user.password is not None:
            cmd.extend(['-p', user.password])
        cmd.extend(['-s', user.shell])
        cmd.extend(['-u', user.uid])
        cmd.append(username)

        # Execute usermod
        cmd = self._strcnv(cmd)
        common.run_command(cmd)
        self.user_set_gecos(user)
        self.user_set_pass_options(user)

    def user_set_gecos(self, user):
        cmd = ['chfn']
        cmd.extend(['-f', user.rname])
        cmd.extend(['-r', user.office])
        cmd.extend(['-w', user.wphone])
        cmd.extend(['-h', user.hphone])
        cmd.extend(['-o', user.other])
        cmd.append(user.name)
        #Execute chfn
        cmd = self._strcnv(cmd)
        common.run_command(cmd)

    def user_set_pass_options(self, user):
        cmd = ['chage']
        cmd.extend(['-d', user.lstchg])
        cmd.extend(['-E', user.expire])
        cmd.extend(['-I', user.inact])
        cmd.extend(['-m', user.min])
        cmd.extend(['-M', user.max])
        cmd.extend(['-W', user.warn])
        cmd.append(user.name)
        # Execute chage
        cmd = self._strcnv(cmd)
        common.run_command(cmd)

    @classmethod
    def delete_user(cls, user, remove_home=False):
        """Delete a user."""
        cmd = ['userdel']
        if remove_home:
            cmd.append('-r')
        cmd.append(user.name)
        common.run_command(cmd)

    @classmethod
    def add_user_to_groups(cls, user, groups):
        """Add a user to a group."""
        groups = ','.join([gr.name for gr in groups])
        common.run_command(['usermod', '-a', '-G', groups, user.name])

    @classmethod
    def remove_user_from_groups(cls, user, groups):
        """Remove a user from a group."""
        groups = [gr.name for gr in groups]
        new_groups = [group for group in user.groups if group not in groups]
        new_groups_str = ','.join(new_groups)
        common.run_command(['usermod', '-G', new_groups_str, user.name])

    @classmethod
    def lock_user(cls, user):
        """Lock a certain user."""
        common.run_command(['usermod', '-L', user.name])

    @classmethod
    def unlock_user(cls, user):
        """Unlock a certain user."""
        common.run_command(['usermod', '-U', user.name])

    @classmethod
    def user_is_locked(cls, user):
        return user.password is None or user.password[0] in "!*"

    def load(self):
        """Generic operations."""
        pwds = pwd.getpwall()
        spwds = spwd.getspall()
        val = {}
        for num in spwds:
            val[num.sp_nam] = num

        for pas in pwds:
            if pas.pw_name in val:
                num = val[pas.pw_name]
            else:
                num = spwd.struct_spwd([None]*9)

            gecos = pas.pw_gecos.split(',', 4)
            gecos += [''] * (5 - len(gecos)) # Pad with empty strings so we have exactly 5 items
            rname, office, wphone, hphone, other = gecos
            usr = User(pas.pw_name, pas.pw_uid, pas.pw_gid, rname, office, wphone, hphone,
                       other, pas.pw_dir, pas.pw_shell, [grp.getgrgid(pas.pw_gid).gr_name], num.sp_lstchg, num.sp_min, num.sp_max, num.sp_warn,
                       num.sp_inact, num.sp_expire, num.sp_pwd)
            self.users[usr.name] = usr

        groups = grp.getgrall()
        for group in groups:
            grup = Group(group.gr_name, group.gr_gid)
            for member in group.gr_mem:
                if member in self.users:
                    ugroups = self.users[member].groups
                    if group.gr_name not in ugroups:
                        self.users[member].groups.append(group.gr_name)
                    grup.members[member] = self.users[member]

            self.groups[group.gr_name] = grup

        for user in self.users.values():
            primary_group = grp.getgrgid(user.gid).gr_name
            if primary_group in self.groups:
                self.groups[primary_group].members[user.name] = user

    def reload(self):
        self.users = {}
        self.groups = {}
        self.load()
        self.libuser_event.notify('event')

    @classmethod
    def get_valid_shells(cls):
        """Check validity of shells."""
        try:
            _file = open("/etc/shells")
            shells = [line.strip() for line in _file.readlines() if line.strip()[0] != '#']
            _file.close()
        except:
            shells = []

        return shells

    @classmethod
    def uid_is_valid(cls, uid):
        """Check validity of user id."""
        return uid >= FIRST_SYSTEM_UID and uid <= LAST_UID

    @classmethod
    def gid_is_valid(cls, gid):
        """Check validity of group id."""
        return gid >= FIRST_SYSTEM_GID and gid <= LAST_GID

    def uid_is_free(self, uid):
        """Check if user id is free."""
        return self.uid_is_valid(uid) and uid not in [user.uid for user in self.users.values()]

    def gid_is_free(self, gid):
        """Check if group id is free."""
        return self.gid_is_valid(gid) and gid not in [group.gid for group in self.groups.values()]

    def get_free_uids(self, _starting=FIRST_UID, _ending=LAST_UID):
        """Find and returns free user ids."""
        used_uids = [user.uid for user in self.users.values()]

        free_uids = range(FIRST_UID, LAST_UID+1)
        for uid in used_uids:
            free_uids.remove(uid)

        return free_uids

    @classmethod
    def name_is_valid(cls, name):
        """Check validity of the name."""
        return re.match(NAME_REGEX, name)

    @classmethod
    def gecos_is_valid(cls, field):
        """This is for checking gecos *fields*, not entire gecos strings."""
        return ':' not in field and ',' not in field

    def shell_is_valid(self, shell):
        """Check shell validity."""
        return shell in self.get_valid_shells()

    @classmethod
    def encrypt(cls, plainpw):
        """Convert a plain text password to a sha-512 encrypted one."""
        alphabet = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        salt = ''.join([random.choice(alphabet) for i in range(8)])

        return crypt.crypt(plainpw, "$6$%s$" % salt)

    def connect_event(self, func):
        """Event functions."""
        self.libuser_event.connect(func)

    def on_system_changed(self, _event):
        """Event callback."""
        self.reload()

    def on_fd_changed(self, _ignored, filename, _mask):
        """INotifier callback."""
        # For debugging use _watchpoint & _watchpaths
        self.notifier.ignore(filename)
        self.notifier._addWatch(filename, self.mask, False, [self.on_fd_changed])
        self.system_event.notify(filename.path)

SYSTEM = System()

if __name__ == '__main__':
    print("System users:", ', '.join(SYSTEM.users))
    print("\nSystem groups:", ', '.join(SYSTEM.groups))

    def analytical():
        """Show the systmen's users and groups."""
        print("System users:")
        for user in SYSTEM.users.values():
            print(" ", user.name)
            print("   ", ", ".join(user.groups))
        print("\nSystem groups:")
        for group in SYSTEM.groups.values():
            print(" ", group.name)
            print("   ", ", ".join(group.members.keys()))

    analytical()
