# This file is part of sch-scripts, https://launchpad.net/sch-scripts
# Copyright 2009-2018 the sch-scripts team, see AUTHORS.
# SPDX-License-Identifier: GPL-3.0-or-later
# pylint: disable= invalid-name
"""Common functions."""

import subprocess
import datetime

def run_command(cmd, poll=False):
    """Run a command.
    
    Returns either True, on successful completion, or the whole stdout
    and stderr of the command, on error. If poll is set return only the process.
    """
    # Popen doesn't like integers like uid or gid in the command line.
    cmdline = [str(s) for s in cmd]

    p = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if not poll:
        res = p.wait()
        if res == 0:
            return True, p.stdout.read().decode('utf-8')
        else:
            print("Σφάλμα κατά την εκτέλεση εντολής:")
            print(" $ %s" % ' '.join(cmdline))
            print(p.stdout.read().decode('utf-8'))
            err = p.stderr.read().decode('utf-8')
            print(err)
            if err == '':
                err = '\n'
            return False, err
    else:
        return p

def days_since_epoch():
    """Return the days since epoch."""
    epoch = datetime.datetime.utcfromtimestamp(0)
    return (datetime.datetime.today() - epoch).days

def date():
    """Return the current date."""
    return datetime.date.today()
