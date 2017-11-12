#!/usr/bin/python2
#
# Copyright 2017 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#


'''
Hook set sata bus to disk drive.

Syntax:
   satabus=(off|on)

Example:
   satabus=on
'''

import os
import sys
import traceback
from xml.dom import minidom
from vdsm.hook import hooking


def set_sata_bus(domxml):
    for disk in domxml.getElementsByTagName('disk'):
        if disk.getAttribute('device') != "disk":
            continue
        target = disk.getElementsByTagName('target')[0]
        bus = target.getAttribute('bus')
        if bus in ['scsi', 'ide', 'virtio']:
            target.setAttribute('bus', 'sata')


def sata_bus():
    if os.environ.get("satabus") == "on":
        domxml = hooking.read_domxml()
        set_sata_bus(domxml)
        hooking.write_domxml(domxml)


def main():
    try:
        if '--test' in sys.argv:
            test()
        else:
            sata_bus()
    except:
        hooking.exit_hook('satabus hook: [unexpected error]: {0}'.format(
                          traceback.format_exc()))


def test():
    text = """<?xml version="1.0" encoding="utf-8"?>
<domain type="kvm" xmlns:ovirt="http://ovirt.org/vm/tune/1.0">
    <name>test</name>
    <devices>
        <disk device="cdrom" snapshot="no" type="file">
            <target bus="ide" dev="hdc"/>
        </disk>
        <disk device="disk" snapshot="no" type="network">
            <target bus="scsi" dev="sda"/>
        </disk>
        <disk device="disk" snapshot="no" type="network">
            <target bus="virtio" dev="vde"/>
        </disk>
    </devices>
</domain>
"""

    xmldom = minidom.parseString(text)
    set_sata_bus(xmldom)
    print("Disk device after set SATA attribute: \n{0}".format(
          xmldom.toxml(encoding='UTF-8')))


if __name__ == '__main__':
    main()
