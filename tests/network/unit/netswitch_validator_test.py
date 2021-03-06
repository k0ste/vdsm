# Copyright 2016-2018 Red Hat, Inc.
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

import unittest

from vdsm.network import errors as ne
from vdsm.network.netswitch import validator


class ValidationTests(unittest.TestCase):

    def test_adding_a_new_single_untagged_net(self):
        fake_running_bonds = {}
        fake_to_be_added_bonds = {}
        fake_kernel_nics = ['eth0']

        validator.validate_net_configuration(
            'net2', {'nic': 'eth0', 'switch': 'ovs'},
            fake_to_be_added_bonds, fake_running_bonds, fake_kernel_nics)

    def test_edit_single_untagged_net_nic(self):
        fake_running_bonds = {}
        fake_to_be_added_bonds = {}
        fake_kernel_nics = ['eth0', 'eth1']

        validator.validate_net_configuration(
            'net1', {'nic': 'eth1', 'switch': 'ovs'},
            fake_to_be_added_bonds, fake_running_bonds, fake_kernel_nics)

    def test_adding_a_second_untagged_net(self):
        fake_running_bonds = {}
        fake_to_be_added_bonds = {}
        fake_kernel_nics = ['eth0', 'eth1']

        validator.validate_net_configuration(
            'net2', {'nic': 'eth1', 'switch': 'ovs'},
            fake_to_be_added_bonds, fake_running_bonds, fake_kernel_nics)

    def test_add_network_with_non_existing_nic(self):
        fake_running_bonds = {}
        fake_to_be_added_bonds = {}
        fake_kernel_nics = []
        with self.assertRaises(ne.ConfigNetworkError) as e:
            validator.validate_net_configuration(
                'net1', {'nic': 'eth0', 'switch': 'ovs'},
                fake_to_be_added_bonds, fake_running_bonds, fake_kernel_nics)
        self.assertEqual(e.exception.args[0], ne.ERR_BAD_NIC)

    def test_add_network_with_non_existing_bond(self):
        fake_running_bonds = {}
        fake_to_be_added_bonds = {}
        fake_kernel_nics = []
        with self.assertRaises(ne.ConfigNetworkError) as e:
            validator.validate_net_configuration(
                'net1', {'bonding': 'bond1', 'switch': 'ovs'},
                fake_to_be_added_bonds, fake_running_bonds, fake_kernel_nics)
        self.assertEqual(e.exception.args[0], ne.ERR_BAD_BONDING)

    def test_add_network_with_to_be_added_bond(self):
        fake_running_bonds = {}
        fake_to_be_added_bonds = {'bond1': {}}
        fake_kernel_nics = []

        validator.validate_net_configuration(
            'net1', {'bonding': 'bond1', 'switch': 'ovs'},
            fake_to_be_added_bonds, fake_running_bonds, fake_kernel_nics)

    def test_add_network_with_running_bond(self):
        fake_running_bonds = {'bond1': {}}
        fake_to_be_added_bonds = {}
        fake_kernel_nics = []

        validator.validate_net_configuration(
            'net1', {'bonding': 'bond1', 'switch': 'ovs'},
            fake_to_be_added_bonds, fake_running_bonds, fake_kernel_nics)

    def test_add_bond_with_no_slaves(self):
        fake_kernel_nics = []
        nets = {}
        running_nets = {}
        with self.assertRaises(ne.ConfigNetworkError):
            validator.validate_bond_configuration(
                'bond1', {'switch': 'ovs'}, nets, running_nets,
                fake_kernel_nics)

    def test_add_bond_with_one_slave(self):
        fake_kernel_nics = ['eth0']
        nets = {}
        running_nets = {}

        validator.validate_bond_configuration(
            'bond1', {'nics': ['eth0'], 'switch': 'ovs'}, nets,
            running_nets, fake_kernel_nics)

    def test_add_bond_with_one_slave_twice(self):
        fake_kernel_nics = ['eth0']
        nets = {}
        running_nets = {}

        validator.validate_bond_configuration(
            'bond1', {'nics': ['eth0', 'eth0'], 'switch': 'ovs'}, nets,
            running_nets, fake_kernel_nics)

    def test_add_bond_with_two_slaves(self):
        fake_kernel_nics = ['eth0', 'eth1']
        nets = {}
        running_nets = {}

        validator.validate_bond_configuration(
            'bond1', {'nics': ['eth0', 'eth1'], 'switch': 'ovs'}, nets,
            running_nets, fake_kernel_nics)

    def test_add_bond_with_not_existing_slaves(self):
        fake_kernel_nics = []
        nets = {}
        running_nets = {}
        with self.assertRaises(ne.ConfigNetworkError):
            validator.validate_bond_configuration(
                'bond1', {'nics': ['eth0', 'eth1'], 'switch': 'ovs'},
                nets, running_nets, fake_kernel_nics)

    def test_add_bond_with_dpdk(self):
        fake_kernel_nics = []
        nets = {}
        running_nets = {}
        with self.assertRaises(ne.ConfigNetworkError):
            validator.validate_bond_configuration(
                'bond1', {'nics': ['eth0', 'dpdk0'], 'switch': 'ovs'},
                nets, running_nets, fake_kernel_nics)

    def test_remove_bond_attached_to_a_network(self):
        fake_kernel_nics = ['eth0', 'eth1']
        nets = {}
        running_nets = {}

        validator.validate_bond_configuration(
            'bond1', {'remove': True}, nets, running_nets,
            fake_kernel_nics)

    def test_remove_bond_attached_to_network_that_was_removed(self):
        fake_kernel_nics = ['eth0', 'eth1']
        nets = {'net1': {'remove': True}}
        running_nets = {'net1': {'southbound': 'bond1'}}

        validator.validate_bond_configuration(
            'bond1', {'remove': True}, nets, running_nets,
            fake_kernel_nics)

    def test_remove_bond_attached_to_network_that_was_not_removed(self):
        fake_kernel_nics = ['eth0', 'eth1']
        nets = {}
        running_nets = {'net1': {'southbound': 'bond1'}}
        with self.assertRaises(ne.ConfigNetworkError) as e:
            validator.validate_bond_configuration(
                'bond1', {'remove': True}, nets, running_nets,
                fake_kernel_nics)
        self.assertEqual(e.exception.args[0], ne.ERR_USED_BOND)

    def test_remove_bond_attached_to_network_that_will_use_nic(self):
        fake_kernel_nics = ['eth0', 'eth1']
        nets = {'net1': {'nic': 'eth0'}}
        running_nets = {'net1': {'southbound': 'bond1'}}

        validator.validate_bond_configuration(
            'bond1', {'remove': True}, nets, running_nets,
            fake_kernel_nics)

    def test_remove_bond_reattached_to_another_network(self):
        fake_kernel_nics = ['eth0', 'eth1', 'eth2']
        nets = {'net1': {'nic': 'eth0'}, 'net2': {'bonding': 'bond1'}}
        running_nets = {'net1': {'southbound': 'bond1'}}
        with self.assertRaises(ne.ConfigNetworkError) as e:
            validator.validate_bond_configuration(
                'bond1', {'remove': True}, nets, running_nets,
                fake_kernel_nics)
        self.assertEqual(e.exception.args[0], ne.ERR_USED_BOND)
