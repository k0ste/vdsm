#
# Copyright 2011 Red Hat, Inc.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Refer to the README and COPYING files for full details of the license
#

EXTRA_DIST = \
	after_vm_destroy.py \
	before_vm_start.py \
	sudoers.vdsm_hook_vhostmd

install-data-hook:
	chmod 440 $(DESTDIR)$(sysconfdir)/sudoers.d/50_vdsm_hook_vhostmd

install-data-local: install-data-sudoers
	$(MKDIR_P) $(DESTDIR)$(vdsmhooksdir)/before_vm_start
	$(INSTALL_SCRIPT) $(srcdir)/before_vm_start.py \
		$(DESTDIR)$(vdsmhooksdir)/before_vm_start/50_vhostmd
	$(MKDIR_P) $(DESTDIR)$(vdsmhooksdir)/after_vm_destroy
	$(INSTALL_SCRIPT) $(srcdir)/after_vm_destroy.py \
		$(DESTDIR)$(vdsmhooksdir)/after_vm_destroy/50_vhostmd
	$(MKDIR_P) $(DESTDIR)$(vdsmhooksdir)/before_vm_migrate_destination
	$(RM) $(DESTDIR)$(vdsmhooksdir)/before_vm_migrate_destination/50_vhostmd
	$(LN_S) ../before_vm_start/50_vhostmd \
		$(DESTDIR)$(vdsmhooksdir)/before_vm_migrate_destination/50_vhostmd
	$(MKDIR_P) $(DESTDIR)$(vdsmhooksdir)/before_vm_dehibernate
	$(RM) $(DESTDIR)$(vdsmhooksdir)/before_vm_dehibernate/50_vhostmd
	$(LN_S) ../before_vm_start/50_vhostmd \
		$(DESTDIR)$(vdsmhooksdir)/before_vm_dehibernate/50_vhostmd

uninstall-local: uninstall-data-sudoers
	$(RM) $(DESTDIR)$(vdsmhooksdir)/before_vm_start/50_vhostmd
	$(RM) $(DESTDIR)$(vdsmhooksdir)/after_vm_destroy/50_vhostmd
	$(RM) $(DESTDIR)$(vdsmhooksdir)/before_vm_migrate_destination/50_vhostmd
	$(RM) $(DESTDIR)$(vdsmhooksdir)/before_vm_dehibernate/50_vhostmd

install-data-sudoers:
	$(MKDIR_P) $(DESTDIR)$(sysconfdir)/sudoers.d
	$(INSTALL_DATA) $(srcdir)/sudoers.vdsm_hook_vhostmd \
		$(DESTDIR)$(sysconfdir)/sudoers.d/50_vdsm_hook_vhostmd

uninstall-data-sudoers:
	$(RM) $(DESTDIR)$(sysconfdir)/sudoers.d/50_vdsm_hook_vhostmd
