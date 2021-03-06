#
# Copyright 2016 Red Hat, Inc.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from __future__ import absolute_import
from __future__ import division

import errno

import pytest

from .fakesanlock import FakeSanlock
from vdsm.common import concurrent
from vdsm.storage import constants as sc
from vdsm.storage.compat import sanlock


INVALID_ALIGN_SECTOR = [
    # Invalid alignment
    (1024, sc.BLOCK_SIZE_512),
    # Invalid block size
    (sc.ALIGNMENT_1M, 8 * 1024),
]

WRONG_ALIGN_SECTOR = [
    # Wrong alignment
    (sc.ALIGNMENT_8M, sc.BLOCK_SIZE_512),
    # Wrong block size
    (sc.ALIGNMENT_1M, sc.BLOCK_SIZE_4K),
]


DIFFERENT_DISK_SANLOCK_SECTOR = [
    (sc.BLOCK_SIZE_512, sc.BLOCK_SIZE_4K),
    (sc.BLOCK_SIZE_4K, sc.BLOCK_SIZE_512),
]


class ExpectedError(Exception):
    pass


# Managing lockspaces

def test_add_lockspace_sync():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path")
    ls = fs.spaces["lockspace"]
    assert ls["host_id"] == 1
    assert ls["path"] == "path"
    assert ls["offset"] == 0
    assert ls["iotimeout"] == 0
    assert ls["ready"].is_set()


def test_add_lockspace_options():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path", offset=42)
    fs.add_lockspace("lockspace", 1, "path", offset=42, iotimeout=10)
    ls = fs.spaces["lockspace"]
    assert ls["offset"] == 42
    assert ls["iotimeout"] == 10


def test_add_lockspace_async():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path", **{'async': True})
    ls = fs.spaces["lockspace"]
    assert ls["iotimeout"] == 0
    assert not ls["ready"].is_set()


@pytest.mark.parametrize(
    "disk_sector, sanlock_sector", DIFFERENT_DISK_SANLOCK_SECTOR)
def test_write_lockspace_wrong_sector(disk_sector, sanlock_sector):
    fs = FakeSanlock(disk_sector)
    with pytest.raises(fs.SanlockException) as e:
        fs.write_lockspace("lockspace", "path", sector=sanlock_sector)
    assert e.value.errno == errno.EINVAL


def test_rem_lockspace_sync():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path")
    fs.rem_lockspace("lockspace", 1, "path")
    assert "host_id" not in fs.spaces["lockspace"]


def test_rem_lockspace_async():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path")
    fs.rem_lockspace("lockspace", 1, "path", **{'async': True})
    ls = fs.spaces["lockspace"]
    assert not ls["ready"].is_set()


def test_rem_lockspace_while_holding_lock():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path")
    fd = fs.register()
    fs.acquire("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    fs.rem_lockspace("lockspace", 1, "path", **{"async": True})

    # Fake sanlock return special None value when sanlock is in process of
    # releasing host_id.
    acquired = fs.inq_lockspace("lockspace", 1, "path")
    assert acquired is None

    # Finish rem_lockspace.
    fs.complete_async("lockspace")

    # Lock shouldn't be hold any more.
    acquired = fs.inq_lockspace("lockspace", 1, "path")
    assert acquired is not None
    assert not acquired


def test_inq_lockspace_acquired():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path")
    acquired = fs.inq_lockspace("lockspace", 1, "path")
    assert acquired


def test_inq_lockspace_acquring_no_wait():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path", **{'async': True})
    acquired = fs.inq_lockspace("lockspace", 1, "path")
    assert acquired is None


def test_inq_lockspace_acquiring_wait():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path", **{'async': True})

    t = concurrent.thread(fs.complete_async, args=("lockspace",))
    t.start()
    try:
        acquired = fs.inq_lockspace("lockspace", 1, "path", wait=True)
    finally:
        t.join()
    assert acquired


def test_inq_lockspace_released():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path")
    fs.rem_lockspace("lockspace", 1, "path")
    acquired = fs.inq_lockspace("lockspace", 1, "path")
    assert not acquired


def test_inq_lockspace_releasing_no_wait():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path")
    fs.rem_lockspace("lockspace", 1, "path", **{'async': True})
    acquired = fs.inq_lockspace("lockspace", 1, "path")
    assert not acquired


def test_inq_lockspace_releasing_wait():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path")
    fs.rem_lockspace("lockspace", 1, "path", **{'async': True})

    t = concurrent.thread(fs.complete_async, args=("lockspace",))
    t.start()
    try:
        acquired = fs.inq_lockspace("lockspace", 1, "path", wait=True)
    finally:
        t.join()
    assert not acquired


# Writing and reading resources

def test_write_read_resource():
    fs = FakeSanlock()
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    info = fs.read_resource("path", 1048576)
    expected = {
        "resource": "resource",
        "lockspace": "lockspace",
        "version": 0,
        "acquired": False,
        "align": sc.ALIGNMENT_1M,
        "sector": sc.BLOCK_SIZE_512,
    }
    assert info == expected


def test_non_existing_resource():
    fs = FakeSanlock()
    with pytest.raises(fs.SanlockException) as e:
        fs.read_resource("path", 1048576)
    assert e.value.errno == fs.SANLK_LEADER_MAGIC


def test_write_resource_failure():
    fs = FakeSanlock()
    fs.errors["write_resource"] = ExpectedError
    with pytest.raises(ExpectedError):
        fs.write_resource("lockspace", "resource", [("path", 1048576)])
    with pytest.raises(fs.SanlockException) as e:
        fs.read_resource("path", 1048576)
    assert e.value.errno == fs.SANLK_LEADER_MAGIC


@pytest.mark.parametrize("align, sector", INVALID_ALIGN_SECTOR)
def test_write_resource_invalid_align_sector(align, sector):
    fs = FakeSanlock()
    disks = [("path", 0)]
    with pytest.raises(ValueError):
        fs.write_resource(
            "ls_name", "res_name", disks, align=align, sector=sector)


@pytest.mark.parametrize(
    "disk_sector, sanlock_sector", DIFFERENT_DISK_SANLOCK_SECTOR)
def test_write_resource_wrong_sector(disk_sector, sanlock_sector):
    fs = FakeSanlock(disk_sector)
    disks = [("path", 0)]
    # Real sanlock succeeds even with wrong sector size.
    fs.write_resource("ls_name", "res_name", disks, sector=sanlock_sector)


def test_read_resource_failure():
    fs = FakeSanlock()
    fs.errors["read_resource"] = ExpectedError
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    with pytest.raises(ExpectedError):
        fs.read_resource("path", 1048576)


@pytest.mark.parametrize("align, sector", INVALID_ALIGN_SECTOR)
def test_read_resource_invalid_align_sector(align, sector):
    fs = FakeSanlock()
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    with pytest.raises(ValueError):
        fs.read_resource("path", 1048576, align=align, sector=sector)


@pytest.mark.parametrize("align, sector", WRONG_ALIGN_SECTOR)
def test_read_resource_wrong_align_sector(align, sector):
    fs = FakeSanlock()
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    with pytest.raises(fs.SanlockException) as e:
        fs.read_resource("path", 1048576, align=align, sector=sector)
    assert e.value.errno == errno.EINVAL


@pytest.mark.parametrize(
    "disk_sector, sanlock_sector", DIFFERENT_DISK_SANLOCK_SECTOR)
def test_read_resource_wrong_sector(disk_sector, sanlock_sector):
    fs = FakeSanlock(disk_sector)
    fs.write_resource(
        "lockspace", "resource", [("path", 1048576)], sector=disk_sector)
    with pytest.raises(fs.SanlockException) as e:
        fs.read_resource("path", 1048576, sector=sanlock_sector)
    assert e.value.errno == errno.EINVAL


# Connecting to the sanlock daemon
def test_register():
    fs = FakeSanlock()
    assert fs.register() == 42


# Acquiring and releasing resources
def test_acquire():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path")
    fd = fs.register()
    fs.acquire("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    res = fs.read_resource("path", 1048576)
    assert res["acquired"]
    assert fs.spaces["lockspace"]["host_id"] == res["host_id"]
    assert fs.hosts[1]["generation"] == res["generation"]


def test_acquire_no_lockspace():
    fs = FakeSanlock()
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fd = fs.register()
    with pytest.raises(fs.SanlockException) as e:
        fs.acquire("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    assert e.value.errno == errno.ENOSPC


def test_acquire_lockspace_adding():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path", **{'async': True})
    fd = fs.register()
    with pytest.raises(fs.SanlockException) as e:
        fs.acquire("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    assert e.value.errno == errno.ENOSPC


def test_acquire_an_acquired_resource():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path")
    fd = fs.register()
    fs.acquire("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    with pytest.raises(fs.SanlockException) as e:
        fs.acquire("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    assert e.value.errno == errno.EEXIST
    res = fs.read_resource("path", 1048576)
    assert res["acquired"]


def test_release():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path")
    fd = fs.register()
    fs.acquire("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    fs.release("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    res = fs.read_resource("path", 1048576)
    assert not res["acquired"]
    # The resource has been released and the owner is zeroed
    assert res["host_id"] == 0
    assert fs.hosts[1]["generation"] == res["generation"]


def test_release_not_acquired():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path")
    fd = fs.register()
    with pytest.raises(fs.SanlockException) as e:
        fs.release("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    assert e.value.errno == errno.EPERM


def test_release_no_lockspace():
    fs = FakeSanlock()
    with pytest.raises(fs.SanlockException) as e:
        fs.release("lockspace", "resource", [("path", 1048576)])
    assert e.value.errno == errno.ENOSPC


def test_read_resource_owners_lockspace_not_initialized():
    fs = FakeSanlock()
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    with pytest.raises(fs.SanlockException) as e:
        fs.read_resource_owners(
            "lockspace", "resource", [("path", 1048576)])
    assert e.value.errno == errno.EINVAL


def test_read_resource_owners_no_owner():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path")
    owners = fs.read_resource_owners("lockspace",
                                     "resource",
                                     [("path", 1048576)])
    assert len(owners) == 0


def test_read_resource_owners():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path")
    fd = fs.register()
    fs.acquire("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    owners = fs.read_resource_owners("lockspace",
                                     "resource",
                                     [("path", 1048576)])
    assert len(owners) == 1
    assert owners[0]["host_id"] == 1
    assert owners[0]["generation"] == 0


def test_read_resource_owners_resource_released():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path")
    fd = fs.register()
    fs.acquire("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    fs.release("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    owners = fs.read_resource_owners(
        "lockspace", "resource", [("path", 1048576)])
    assert owners == []


def test_read_resource_owners_lockspace_removed():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path")
    fd = fs.register()
    fs.acquire("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    fs.release("lockspace", "resource", [("path", 1048576)], slkfd=fd)
    fs.rem_lockspace("lockspace", 1, "path")
    owners = fs.read_resource_owners(
        "lockspace", "resource", [("path", 1048576)])
    assert owners == []


@pytest.mark.parametrize("align, sector", INVALID_ALIGN_SECTOR)
def test_read_resource_owners_invalid_align_sector(align, sector):
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    disks = [("path", 1048576)]
    with pytest.raises(ValueError):
        fs.read_resource_owners(
            "lockspace", "path", disks, align=align, sector=sector)


@pytest.mark.parametrize("align, sector", WRONG_ALIGN_SECTOR)
def test_read_resource_owners_wrong_align_sector(align, sector):
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    disks = [("path", 1048576)]
    with pytest.raises(fs.SanlockException) as e:
        fs.read_resource_owners(
            "lockspace", "path", disks, align=align, sector=sector)
    assert e.value.errno == errno.EINVAL


@pytest.mark.parametrize(
    "disk_sector, sanlock_sector", DIFFERENT_DISK_SANLOCK_SECTOR)
def test_read_resource_owners_wrong_sector(disk_sector, sanlock_sector):
    fs = FakeSanlock(disk_sector)
    fs.write_lockspace("lockspace", "path", sector=disk_sector)
    fs.write_resource(
        "lockspace", "resource", [("path", 1048576)], sector=disk_sector)
    disks = [("path", 1048576)]
    with pytest.raises(fs.SanlockException) as e:
        fs.read_resource_owners(
            "lockspace", "path", disks, sector=sanlock_sector)
    assert e.value.errno == errno.EINVAL


def test_get_hosts():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path")
    host = fs.get_hosts("lockspace", 1)
    assert host[0]["id"] == 1
    assert host[0]["generation"] == 0


def test_get_hosts_no_lockspace():
    fs = FakeSanlock()
    with pytest.raises(fs.SanlockException) as e:
        fs.get_hosts("lockspace", 1)
    assert e.value.errno == errno.ENOSPC


def test_add_lockspace_generation_increase():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    fs.add_lockspace("lockspace", 1, "path")
    fs.rem_lockspace("lockspace", 1, "path")
    fs.add_lockspace("lockspace", 1, "path")
    host = fs.get_hosts("lockspace", 1)
    assert host[0]["id"] == 1
    assert host[0]["generation"] == 1
    assert host[0]["flags"] == sanlock.HOST_LIVE


def test_write_lockspace():
    lockspace = "lockspace"
    fs = FakeSanlock()

    assert lockspace not in fs.spaces

    fs.write_lockspace(lockspace, "/var/tmp/test", offset=0, max_hosts=1)

    expected = {
        "path": "/var/tmp/test",
        "offset": 0,
        "max_hosts": 1,
        "iotimeout": 0,
        "align": sc.ALIGNMENT_1M,
        "sector": sc.BLOCK_SIZE_512,
    }
    assert expected == fs.spaces[lockspace]


@pytest.mark.parametrize("align, sector", INVALID_ALIGN_SECTOR)
def test_write_lockspace_invalid_align_sector(align, sector):
    fs = FakeSanlock()
    with pytest.raises(ValueError):
        fs.write_lockspace("ls_name", "path", align=align, sector=sector)


def test_write_resource():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.write_resource("lockspace", "resource", [("path", 1048576)])
    info = fs.read_resource("path", 1048576)
    expected = {
        "resource": "resource",
        "lockspace": "lockspace",
        "version": 0,
        "acquired": False,
        "align": sc.ALIGNMENT_1M,
        "sector": sc.BLOCK_SIZE_512,
    }
    assert info == expected


def test_add_without_init_lockpsace():
    fs = FakeSanlock()
    with pytest.raises(fs.SanlockException) as e:
        fs.add_lockspace("lockspace", 1, "path")
    assert e.value.errno == fs.SANLK_LEADER_MAGIC


def test_add_lockspace_twice():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    fs.add_lockspace("lockspace", 1, "path")
    with pytest.raises(fs.SanlockException) as e:
        fs.add_lockspace("lockspace", 1, "path")
    assert e.value.errno == errno.EEXIST


def test_add_lockspace_wrong_path():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    with pytest.raises(fs.SanlockException) as e:
        fs.add_lockspace("lockspace", 1, "path2", )
    assert e.value.errno == errno.EINVAL


def test_add_lockspace_wrong_offset():
    fs = FakeSanlock()
    fs.write_lockspace("lockspace", "path")
    with pytest.raises(fs.SanlockException) as e:
        fs.add_lockspace("lockspace", 1, "path", offset=42)
    assert e.value.errno == errno.EINVAL
