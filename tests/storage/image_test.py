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

from __future__ import absolute_import
from __future__ import division

from monkeypatch import MonkeyPatch
import pytest

from storage.storagefakelib import FakeBlockSD
from storage.storagefakelib import FakeFileSD
from storage.storagefakelib import FakeStorageDomainCache

from testlib import expandPermutations, permutations
from testlib import make_config
from testlib import VdsmTestCase

from vdsm.common import constants
from vdsm.storage import constants as sc
from vdsm.storage import image
from vdsm.storage import qemuimg

GB_IN_BLK = 1024**3 // 512
CONFIG = make_config([('irs', 'volume_utilization_chunk_mb', '1024')])


def fakeEstimateChainSizeBlk(self, sdUUID, imgUUID, volUUID, size):
    return GB_IN_BLK * 2.25


def fake_estimate_qcow2_size_blk(self, src_vol_params, dst_sd_id):
    return GB_IN_BLK * 1.25


@expandPermutations
class TestCalculateVolAlloc(VdsmTestCase):

    @permutations([
        # srcVolParams, destVolFormt, expectedAlloc
        # copy raw to raw, using virtual size
        (dict(size=GB_IN_BLK * 2,
              volFormat=sc.RAW_FORMAT,
              apparentsize=GB_IN_BLK),
         sc.RAW_FORMAT,
         GB_IN_BLK * 2),
        # copy raw to qcow, using estimated chain size
        (dict(size=GB_IN_BLK * 2,
              volFormat=sc.RAW_FORMAT,
              apparentsize=GB_IN_BLK,
              prealloc=sc.SPARSE_VOL,
              parent="parentUUID",
              imgUUID="imgUUID",
              volUUID="volUUID"),
         sc.COW_FORMAT,
         GB_IN_BLK * 1.25),
        # copy single cow volume to raw, using virtual size
        (dict(size=GB_IN_BLK * 2,
              volFormat=sc.COW_FORMAT,
              apparentsize=GB_IN_BLK),
         sc.RAW_FORMAT,
         GB_IN_BLK * 2),
        # copy cow chain to raw, using virtual size
        (dict(size=GB_IN_BLK * 2,
              volFormat=sc.COW_FORMAT,
              apparentsize=GB_IN_BLK,
              parent="parentUUID"),
         sc.RAW_FORMAT,
         GB_IN_BLK * 2),
        # copy single cow to cow, using estimated size.
        (dict(size=GB_IN_BLK * 2,
              volFormat=sc.COW_FORMAT,
              apparentsize=GB_IN_BLK,
              parent=sc.BLANK_UUID),
         sc.COW_FORMAT,
         GB_IN_BLK * 1.25),
        # copy qcow chain to cow, using estimated chain size
        (dict(size=GB_IN_BLK * 2,
              volFormat=sc.COW_FORMAT,
              apparentsize=GB_IN_BLK,
              prealloc=sc.SPARSE_VOL,
              parent="parentUUID",
              imgUUID="imgUUID",
              volUUID="volUUID"),
         sc.COW_FORMAT,
         GB_IN_BLK * 2.25),
    ])
    @MonkeyPatch(image.Image, 'estimateChainSizeBlk', fakeEstimateChainSizeBlk)
    @MonkeyPatch(
        image.Image, 'estimate_qcow2_size_blk', fake_estimate_qcow2_size_blk)
    def test_calculate_vol_alloc(
            self, src_params, dest_format, expected_blk):
        img = image.Image("/path/to/repo")
        alloc_blk = img.calculate_vol_alloc_blk("src_sd_id", src_params,
                                                "dst_sd_id", dest_format)
        self.assertEqual(alloc_blk, expected_blk)


class TestEstimateQcow2Size:

    @pytest.mark.parametrize('sd_class', [FakeFileSD, FakeBlockSD])
    def test_raw_to_qcow2_estimated_size(
            self, monkeypatch, sd_class):
        monkeypatch.setattr(image, "config", CONFIG)
        monkeypatch.setattr(
            qemuimg,
            'measure',
            # the estimated size for converting 1 gb
            # raw empty volume to qcow2 format
            # cmd:
            #   qemu-img measure -f raw -O qcow2 test.raw
            # output:
            #   required size: 393216
            #   fully allocated size: 1074135040
            lambda **args: {"required": 393216})
        monkeypatch.setattr(image, 'sdCache', FakeStorageDomainCache())

        image.sdCache.domains['sdUUID'] = sd_class("fake manifest")
        img = image.Image("/path/to/repo")

        vol_params = dict(
            size=constants.GIB,
            volFormat=sc.RAW_FORMAT,
            path='path')
        estimated_size_blk = img.estimate_qcow2_size_blk(vol_params, "sdUUID")

        assert estimated_size_blk == 2097920

    @pytest.mark.parametrize('sd_class', [FakeFileSD, FakeBlockSD])
    def test_qcow2_to_qcow2_estimated_size(
            self, monkeypatch, sd_class):
        monkeypatch.setattr(image, "config", CONFIG)
        monkeypatch.setattr(
            qemuimg,
            'measure',
            # the estimated size for converting 1 gb
            # qcow2 empty volume to qcow2 format
            # cmd:
            #   qemu-img measure -f qcow2 -O qcow2 test.qcow2
            # output:
            #   required size: 393216
            #   fully allocated size: 1074135040
            lambda **args: {"required": 393216})
        monkeypatch.setattr(image, 'sdCache', FakeStorageDomainCache())

        image.sdCache.domains['sdUUID'] = sd_class("fake manifest")
        img = image.Image("/path/to/repo")

        vol_params = dict(
            size=constants.GIB,
            volFormat=sc.COW_FORMAT,
            path='path')
        estimated_size_blk = img.estimate_qcow2_size_blk(vol_params, "sdUUID")

        assert estimated_size_blk == 2097920

    @pytest.mark.parametrize("storage,format,prealloc,estimate,expected", [
        # File raw preallocated, avoid prealocation.
        ("file", sc.RAW_FORMAT, sc.PREALLOCATED_VOL, 20971520, 0),

        # File - anything else no initial size.
        ("file", sc.RAW_FORMAT, sc.SPARSE_VOL, 20971520, None),
        ("file", sc.COW_FORMAT, sc.SPARSE_VOL, 20971520, None),
        ("file", sc.COW_FORMAT, sc.PREALLOCATED_VOL, 20971520, None),

        # Block qcow2 thin, return estimate.
        ("block", sc.COW_FORMAT, sc.SPARSE_VOL, 20971520, 20971520),

        # Block - anything else no initial size.
        ("block", sc.COW_FORMAT, sc.PREALLOCATED_VOL, 20971520, None),
        ("block", sc.RAW_FORMAT, sc.PREALLOCATED_VOL, 20971520, None),
    ])
    def test_calculate_initial_size_blk_file_raw_prealloc(
            self, storage, format, prealloc, estimate, expected):
        img = image.Image("/path")
        initial_size_blk = img.calculate_initial_size_blk(
            storage == "file", format, prealloc, estimate)

        assert initial_size_blk == expected
