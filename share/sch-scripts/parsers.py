# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Parsers."""

import csv
import os
import configparser
from io import StringIO, BytesIO
import libuser

FIELDS_MAP = {'Όνομα χρήστη': 'name', 'Τελευταία αλλαγή κωδικού': 'lstchg', 'Κύρια ομάδα': 'gid', 'Όνομα κύριας ομάδας' : 'primary_group', 'Κέλυφος': 'shell', 'UID': 'uid', 'Γραφείο': 'office', 'Κρυπτογραφημένος κωδικός': 'password', 'Κωδικός': 'plainpw', 'Λήξη': 'expire', 'Μέγιστη διάρκεια': 'max', 'Προειδοποίηση': 'warn', 'Κατάλογος': 'directory', 'Ελάχιστη διάρκεια': 'min', 'Άλλο': 'other', 'Ομάδες': 'groups', 'Τηλ. γραφείου': 'wphone', 'Ανενεργός': 'inact', 'Ονοματεπώνυμο': 'rname', 'Τηλ. οικίας': 'hphone'}

class CSV:
    """Parser for Comma-separated values."""

    def __init__(self):
        self.fields_map = FIELDS_MAP

    def parse(self, fname):
        users_dict = csv.DictReader(open(fname))
        users = {}
        groups = {}
        for user_d in users_dict:
            user = libuser.User()

            for key, value in user_d.items():
                try:
                    user.__dict__[self.fields_map[key]] = value # FIXME: Here we lose the datatype
                except:
                    pass
            # Try to convert the numbers from string to int
            int_attributes = ['lstchg', 'gid', 'uid', 'expire', 'max', 'warn', 'min', 'inact']
            for attr in int_attributes:
                try:
                    user.__dict__[attr] = int(user.__dict__[attr])
                except ValueError:
                    user.__dict__[attr] = None
            # If plainpw is set, override and update password
            if user.plainpw:
                user.password = libuser.SYSTEM.encrypt(user.plainpw)

            if user.name:
                users[user.name] = user
                user_groups_string = user.groups
                user.groups = []
                for grup in user_groups_string.split(','):
                    pair = grup.split(':')
                    if len(pair) == 2:
                        gname, gid = pair
                        try:
                            gid = int(gid)
                        except ValueError:
                            gid = None
                    else: # There is no GID specified for this group
                        gname = grup
                        gid = None
                    if gname != '':
                        user.groups.append(gname)

                    # Create Group instances from memberships
                    if gname not in groups:
                        groups[gname] = libuser.Group(gname, gid)
                    groups[gname].members[user.name] = user

                if user.groups == '':
                    user.groups = None

        return libuser.Set(users, groups)


    def write(self, fname, system, users):
        _file = open(fname, 'w')
        writer = csv.DictWriter(_file, fieldnames=libuser.CSV_USER_FIELDS)
        writer.writerow(dict((n, n) for n in libuser.CSV_USER_FIELDS))
        for user in users:
            u_dict = dict((key, user.__dict__[o_key] if user.__dict__[o_key] is not None else '') for key, o_key in self.fields_map.items())
            u_dict['Κωδικός'] = '' # We don't have the plain password
            u_dict['Ομάδες'] = list(u_dict['Ομάδες'])
            # Convert the groups value to a proper gname:gid pairs formatted string
            final_groups = u_dict['Ομάδες']
            final_groups.remove(u_dict['Όνομα κύριας ομάδας'])
            for i, gname in enumerate(final_groups):
                gid = system.groups[gname].gid
                final_groups[i] = ':'.join((final_groups[i], str(gid)))
            u_dict['Ομάδες'] = ','.join(final_groups)

            writer.writerow(u_dict)
        _file.close()


class Passwd():
    """Parser for password."""

    # passwd format: username:password (or x):UID:GID:gecos:home:shell
    # shadow format: username:password (or */!):last change:min:max:warn:inact:expire:reserved
    # group format: group_name:password (or x):GID:user_list
    # gshadow format: Not Implemented
    def __init__(self):
        pass

    @classmethod
    def parse(cls, pwd, spwd=None, grp=None):
        new_set = libuser.Set()

        with open(pwd) as _file:
            reader = csv.reader(_file, delimiter=':', quoting=csv.QUOTE_NONE)
            for row in reader:
                usr = libuser.User()
                usr.name = row[0]
                usr.password = row[1]
                usr.uid = int(row[2])
                usr.gid = int(row[3])
                gecos = row[4].split(',', 4)
                gecos += [''] * (5 - len(gecos)) # Pad with empty strings so we have exactly 5 items
                usr.rname, usr.office, usr.wphone, usr.hphone, usr.other = gecos
                usr.directory = row[5]
                usr.shell = row[6]
                new_set.add_user(usr)

        if spwd:
            with open(spwd) as _file:
                reader = csv.reader(_file, delimiter=':', quoting=csv.QUOTE_NONE)
                for row in reader:
                    name = row[0]
                    usr = new_set.users[name] # The user must exist in passwd
                    usr.password = row[1]
                    nums = ['lstchg', 'min', 'max', 'warn', 'inact', 'expire']
                    for i, att in enumerate(nums, 2):
                        try:
                            usr.__dict__[att] = int(row[i])
                        except:
                            pass

        if grp:
            with open(grp) as _file:
                reader = csv.reader(_file, delimiter=':', quoting=csv.QUOTE_NONE)
                gids_map = {} # This is only used to set the primary_group User attribute
                for row in reader:
                    grup = libuser.Group()
                    grup.name = row[0]
                    grup.gid = int(row[2])
                    members = row[3].split(',')
                    if members == ['']:
                        members = []
                    grup.members = {}
                    for name in members:
                        grup.members[name] = new_set.users[name]
                        new_set.users[name].groups.append(grup.name)

                    new_set.add_group(grup)
                    gids_map[grup.gid] = grup.name

                for usr in new_set.users.values():
                    usr.primary_group = gids_map[usr.gid]
                    if usr.primary_group in usr.groups:
                        usr.groups.remove(usr.primary_group)
                    #usr.groups.append(usr.primary_group)

        return new_set


class DHCP():
    """Parser for Dynamic Host Configuration Protocol."""

    def __init__(self):
        self.dhcp_info = {}

    def parse(self, interface):
        config_file = None
        file_run = '/run/net-%s.conf' % interface
        file_tmp = '/tmp/net-%s.conf' % interface
        if os.path.isfile(file_run):
            config_file = file_run
        elif os.path.isfile(file_tmp):
            config_file = file_tmp

        if not config_file:
            return

        vconfig_file = StringIO('[Root]\n%s' % open(config_file).read())
        config = configparser.ConfigParser(allow_no_value=True)
        config.readfp(vconfig_file)
        try:
            ip_add = config.get('Root', 'ipv4addr').strip("'")
        except configparser.NoOptionError:
            return

        mask = config.get('Root', 'ipv4netmask').strip("'")
        route = config.get('Root', 'ipv4gateway').strip("'")

        try:
            _dns0 = config.get('Root', 'ipv4dns0').strip("'")
        except configparser.NoOptionError:
            _dns0 = None

        try:
            _dns1 = config.get('Root', 'ipv4dns1').strip("'")
        except configparser.NoOptionError:
            _dns1 = None

        try:
            _dns2 = config.get('Root', 'ipv4dns2').strip("'")
        except configparser.NoOptionError:
            _dns2 = None

        dnss = sorted([value for key, value in locals().items() if key.startswith('dns') and value and value != '0.0.0.0'])

        self.dhcp_info.update(ip_add=ip_add, mask=mask, route=route, dnss=dnss)

        return self.dhcp_info
