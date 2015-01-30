#!/usr/bin/env python
#
# add_file.py - test cases for the COTAddFile class
#
# January 2015, Glenn F. Matthews
# Copyright (c) 2013-2015 the COT project developers.
# See the COPYRIGHT.txt file at the top-level directory of this distribution
# and at https://github.com/glennmatthews/cot/blob/master/COPYRIGHT.txt.
#
# This file is part of the Common OVF Tool (COT) project.
# It is subject to the license terms in the LICENSE.txt file found in the
# top-level directory of this distribution and at
# https://github.com/glennmatthews/cot/blob/master/LICENSE.txt. No part
# of COT, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE.txt file.

import os.path

from COT.tests.ut import COT_UT
from COT.ui_shared import UI
from COT.add_file import COTAddFile
from COT.data_validation import InvalidInputError


class TestCOTAddFile(COT_UT):
    """Test cases for the COTAddFile module"""
    def setUp(self):
        """Test case setup function called automatically prior to each test."""
        super(TestCOTAddFile, self).setUp()
        self.instance = COTAddFile(UI())
        self.instance.set_value("output", self.temp_file)

    def test_readiness(self):
        """Test ready_to_run() under various combinations of parameters."""
        ready, reason = self.instance.ready_to_run()
        self.assertFalse(ready)
        self.assertEqual("FILE is a mandatory argument!", reason)
        self.assertRaises(InvalidInputError, self.instance.run)

        self.instance.set_value("FILE", self.iosv_ovf)
        ready, reason = self.instance.ready_to_run()
        self.assertFalse(ready)
        self.assertEqual("PACKAGE is a mandatory argument!", reason)
        self.assertRaises(InvalidInputError, self.instance.run)

        self.instance.set_value("PACKAGE", self.input_ovf)
        ready, reason = self.instance.ready_to_run()
        self.assertTrue(ready)

    def test_add_file(self):
        """Basic file addition"""
        self.instance.set_value("PACKAGE", self.input_ovf)
        self.instance.set_value("FILE", self.iosv_ovf)
        self.instance.run()
        self.instance.finished()
        self.check_diff("""
     <ovf:File ovf:href="input.iso" ovf:id="file2" ovf:size="{iso_size}" />
+    <ovf:File ovf:href="iosv.ovf" ovf:id="iosv.ovf" ovf:size="{ovf_size}" />
   </ovf:References>
""".format(iso_size=self.FILE_SIZE['input.iso'],
           ovf_size=os.path.getsize(self.iosv_ovf)))

    def test_add_file_with_id(self):
        """Add a file with explicit 'file_id' argument."""
        self.instance.set_value("PACKAGE", self.input_ovf)
        self.instance.set_value("FILE", self.iosv_ovf)
        self.instance.set_value("file_id", "myfile")
        self.instance.run()
        self.instance.finished()
        self.check_diff("""
     <ovf:File ovf:href="input.iso" ovf:id="file2" ovf:size="{iso_size}" />
+    <ovf:File ovf:href="iosv.ovf" ovf:id="myfile" ovf:size="{ovf_size}" />
   </ovf:References>
""".format(iso_size=self.FILE_SIZE['input.iso'],
           ovf_size=os.path.getsize(self.iosv_ovf)))

    def test_overwrite_file(self):
        self.instance.set_value("PACKAGE", self.input_ovf)
        self.instance.set_value("FILE", os.path.join(
            os.path.dirname(__file__), 'input.iso'))
        self.instance.run()
        self.instance.finished()
        self.check_diff("")

    def test_add_file_then_change_to_disk(self):
        """Add a disk as a file, then make it a proper disk."""
        self.instance.set_value("PACKAGE", self.minimal_ovf)
        intermediate_ovf = os.path.join(self.temp_dir, "mid.ovf")
        self.instance.set_value("output", intermediate_ovf)
        disk_file = os.path.join(os.path.dirname(__file__), "blank.vmdk")
        self.instance.set_value("FILE", disk_file)
        self.instance.set_value("file_id", "mydisk")
        self.instance.run()
        self.instance.finished()
        self.check_diff(file1=self.minimal_ovf,
                        file2=intermediate_ovf,
                        expected="""
 <ovf:Envelope xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1">
-  <ovf:References />
+  <ovf:References>
+    <ovf:File ovf:href="blank.vmdk" ovf:id="mydisk" ovf:size="{0}" />
+  </ovf:References>
   <ovf:VirtualSystem ovf:id="x">
""".format(self.FILE_SIZE['blank.vmdk']))

        from COT.add_disk import COTAddDisk
        ad = COTAddDisk(UI())
        ad.set_value("PACKAGE", intermediate_ovf)
        ad.set_value("output", self.temp_file)
        ad.set_value("DISK_IMAGE", disk_file)
        ad.set_value("file_id", "mydisk")
        ad.run()
        ad.finished()
        ad.destroy()
        self.check_diff(file1=intermediate_ovf, expected="""
 <?xml version='1.0' encoding='utf-8'?>
-<ovf:Envelope xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1">
+<ovf:Envelope xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1" \
xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/\
CIM_ResourceAllocationSettingData">
   <ovf:References>
...
   </ovf:References>
+  <ovf:DiskSection>
+    <ovf:Info>Virtual disk information</ovf:Info>
+    <ovf:Disk ovf:capacity="512" ovf:capacityAllocationUnits="byte * 2^20" \
ovf:diskId="mydisk" ovf:fileRef="mydisk" ovf:format="http://www.vmware.com/\
interfaces/specifications/vmdk.html#streamOptimized" />
+  </ovf:DiskSection>
   <ovf:VirtualSystem ovf:id="x">
...
       <ovf:Info />
+      <ovf:Item>
+        <rasd:Address>0</rasd:Address>
+        <rasd:Description>IDE Controller 0</rasd:Description>
+        <rasd:ElementName>IDE Controller</rasd:ElementName>
+        <rasd:InstanceID>1</rasd:InstanceID>
+        <rasd:ResourceType>5</rasd:ResourceType>
+      </ovf:Item>
+      <ovf:Item>
+        <rasd:AddressOnParent>0</rasd:AddressOnParent>
+        <rasd:ElementName>Hard Disk Drive</rasd:ElementName>
+        <rasd:HostResource>ovf:/disk/mydisk</rasd:HostResource>
+        <rasd:InstanceID>2</rasd:InstanceID>
+        <rasd:Parent>1</rasd:Parent>
+        <rasd:ResourceType>17</rasd:ResourceType>
+      </ovf:Item>
     </ovf:VirtualHardwareSection>
""")
