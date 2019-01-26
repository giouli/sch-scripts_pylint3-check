# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
# pylint: disable= invalid-name
"""Configuration handling."""

import configparser
import os

PATH = os.path.expanduser('~/.config/sch-scripts/')
SETTINGS_F = os.path.join(PATH, 'settings')

GUI_DEFAULTS = {'show_system_groups' : False,
                'show_private_groups' : False,
                'visible_user_columns' : 'all',
                'requests_checked_roles' : '',
                'requests_checked_groups' : ''
               }
ROLES_DEFAULTS = {
    'καθηγητής' : 'adm,cdrom,epoptes,fuse,plugdev,sambashare,vboxusers,$$teachers',
    'διαχειριστής' : 'adm,cdrom,dip,epoptes,fuse,lpadmin,plugdev,'
                     'sambashare,sudo,vboxusers,$$teachers',
    'μαθητής' : 'fuse,sambashare,vboxusers',
    'προσωπικό' : 'adm,cdrom,fuse,plugdev,sambashare,vboxusers'
}

PARSER = configparser.ConfigParser()

def save():
    """Save the changes in settings."""
    f = open(SETTINGS_F, 'w')
    PARSER.write(f)
    f.close()

def setdefaults(overwrite=False):
    """Set the default attributes."""
    if not PARSER.has_section('GUI'):
        PARSER.add_section('GUI')

    for k, v in GUI_DEFAULTS.items():
        if overwrite or not PARSER.has_option('GUI', k):
            PARSER.set('GUI', k, str(v))

    if not PARSER.has_section('Roles'):
        PARSER.add_section('Roles')

    for k, v in ROLES_DEFAULTS.items():
        # TODO: new sch-scripts versions are not able to append groups like
        # 'fuse' to the saved user Roles, so don't read the user settings
        # at all until we reapproach the issue.
        # if overwrite or not PARSER.has_option('Roles', k):
        PARSER.set('Roles', k, str(v))


    save()

if not os.path.isdir(PATH):
    os.makedirs(PATH)

if not os.path.isfile(SETTINGS_F):
    setdefaults()

PARSER.read(SETTINGS_F)
setdefaults()
