# Copyright (C) 2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
"""
userstorage.py - configure storage for vdsm storage tests.
"""

from __future__ import absolute_import
from __future__ import division

import argparse
import errno
import logging
import os
import subprocess

# because this is used both as script and as a module, we don't import any vdsm
# module here. Importing vdsm modules requires changing PYTHONPATH to run this
# script.

BASE_DIR = "/var/tmp/vdsm-storage"

log = logging.getLogger()


class Unsupported(Exception):
    """
    Raised if configuration is not supported in the testing environment.
    """


class File(object):

    def __init__(self, name, size, sector_size=512):
        """
        Create file based storage.
        """
        self.name = name
        self.size = size
        self.sector_size = sector_size
        self.loop = os.path.join(BASE_DIR, "loop." + name)
        self.backing = os.path.join(BASE_DIR, "backing." + name)
        self.mountpoint = os.path.join(BASE_DIR, "mount." + name)
        self.path = os.path.join(self.mountpoint, "file")

    def setup(self):
        # Detecting unsupported environment automatically makes it easy to run
        # the tests everywhere without any configuration.
        if self.sector_size == 4096:
            if not HAVE_SECTOR_SIZE or "OVIRT_CI" in os.environ:
                raise Unsupported("Sector size {} not supported"
                                  .format(self.sector_size))

        if not os.path.exists(self.loop):
            self._create_loop_device()
            self._create_filesystem()
            self._create_file()

    def teardown(self):
        if self._is_mounted():
            self._remove_filesystem()
        _remove_dir(self.mountpoint)
        if os.path.exists(self.loop):
            self._remove_loop_device()
        _remove_file(self.backing)

    def _create_loop_device(self):
        log.info("Creating loop device %s", self.loop)

        with open(self.backing, "w") as f:
            f.truncate(self.size)

        cmd = [
            "sudo",
            "losetup",
            "-f", self.backing,
            "--show",
        ]

        if HAVE_SECTOR_SIZE:
            cmd.append("--sector-size")
            cmd.append(str(self.sector_size))

        out = subprocess.check_output(cmd)
        device = out.decode("utf-8").strip()

        # Remove stale symlink.
        if os.path.islink(self.loop):
            os.unlink(self.loop)

        os.symlink(device, self.loop)

        if os.geteuid() != 0:
            _chown(self.loop)

    def _remove_loop_device(self):
        log.info("Removing loop device %s", self.loop)
        subprocess.check_call(["sudo", "losetup", "-d", self.loop])
        _remove_file(self.loop)

    def _create_filesystem(self):
        log.info("Creating filesystem %s", self.mountpoint)

        # TODO: Use -t xfs (requires xfsprogs package).
        subprocess.check_call(["sudo", "mkfs", "-q", self.loop])
        _create_dir(self.mountpoint)
        subprocess.check_call(["sudo", "mount", self.loop, self.mountpoint])

        if os.geteuid() != 0:
            _chown(self.mountpoint)

    def _remove_filesystem(self):
        log.info("Removing filesystem %s", self.mountpoint)
        subprocess.check_call(["sudo", "umount", self.mountpoint])

    def _is_mounted(self):
        with open("/proc/self/mounts") as f:
            for line in f:
                if self.mountpoint in line:
                    return True
        return False

    def _create_file(self):
        log.info("Creating file %s", self.path)
        with open(self.path, "w") as f:
            f.truncate(self.size)

    def __str__(self):
        return self.name


def _chown(path):
    user_group = "%(USER)s:%(USER)s" % os.environ
    subprocess.check_call(["sudo", "chown", user_group, path])


def _create_dir(path):
    try:
        os.makedirs(path)
    except EnvironmentError as e:
        if e.errno != errno.EEXIST:
            raise


def _remove_file(path):
    try:
        os.remove(path)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise


def _remove_dir(path):
    try:
        os.rmdir(path)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise


def _have_sector_size():
    out = subprocess.check_output(["losetup", "-h"])
    return "--sector-size <num>" in out.decode()


HAVE_SECTOR_SIZE = _have_sector_size()

PATHS = [
    File("file-512", size=1024**3, sector_size=512),
    File("file-4k", size=1024**3, sector_size=4096),
]


def main():
    parser = argparse.ArgumentParser(
        description='Configure storage for vdsm storage tests')
    parser.add_argument("command", choices=["setup", "teardown"])
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[userstorage] %(levelname)-7s %(message)s")

    if args.command == "setup":
        setup(args)
    elif args.command == "teardown":
        teardown(args)


def setup(args):
    _create_dir(BASE_DIR)
    for p in PATHS:
        try:
            p.setup()
        except Unsupported as e:
            log.warning("Cannot setup %s storage: %s", p.name, e)


def teardown(args):
    for p in PATHS:
        p.teardown()
    _remove_dir(BASE_DIR)


if __name__ == "__main__":
    main()
