#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2017 <+YOU OR YOUR COMPANY+>.
# 
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

import numpy
from gnuradio import gr
import pmt

class variable_setter(gr.sync_block):
    """
    docstring for block variable_setter
    """
    def __init__(self, varname,varsetter,guiupdater,is_pair,key):
        gr.sync_block.__init__(self,
            name="variable_setter",
            in_sig=None,
            out_sig=None)
        self.varname=varname
        self.setvar=varsetter
        self.updateGui=guiupdater
        self.is_pair=is_pair
        self.key=int(key)
        self.message_port_register_in(pmt.intern('in'))
        self.set_msg_handler(pmt.intern('in'), self.handle_msg)
    def handle_msg(self,msg):
      #if self.is_pair:
        #msgkey=pmt.to_python(pmt.car(msg))
        #data=pmt.to_python(pmt.cdr(msg))
        #print("key:%s, data: %s"%(msgkey,data))
      #else:
        #msgkey=self.key#accept all messages in non-pair mode
        #data= pmt.to_python(msg)
      m = pmt.symbol_to_string(msg)
      msgkey=int(m.split()[0])
      data=float(m.split()[1])
      #print("key:%s, data: %s"%(msgkey,data))
      if self.key==msgkey:
        #print(data)
        self.setvar(data)
        self.updateGui(data)
        #print("calling setter on %s"%self.varname)