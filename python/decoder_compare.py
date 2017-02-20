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
import pmt,functools,time

class decoder_compare(gr.sync_block):
    """
    docstring for block decoder_compare
    """
    def __init__(self, nPorts=2):
        gr.sync_block.__init__(self,
            name="decoder_compare",
            in_sig=None,
            out_sig=None)
        if nPorts==1:
          self.message_port_register_in(pmt.intern('in'))
          self.set_msg_handler(pmt.intern('in'), functools.partial(self.handle_msg, port=0))
        else:
          for i in range(nPorts):
            self.message_port_register_in(pmt.intern('in%d'%i))
            self.set_msg_handler(pmt.intern('in%d'%i), functools.partial(self.handle_msg, port=i))
        self.nPorts=nPorts
        self.synced=[False]*nPorts
        self.numErrors=[0]*nPorts
        self.numPackets=[0]*nPorts
        self.printTime=time.time()
    def handle_msg(self,msg,port):
      #print("port:%i, msg:%s"%(port,pmt.to_python(msg)))
      if pmt.to_long(pmt.car(msg))==1L:
        data=pmt.to_python(pmt.cdr(msg))
        #print("port:%i, data: %s"%(port,data))
        self.synced[port]=data
        print("errors:%s,Packets:%s, sync:%s"%(self.numErrors,self.numPackets,self.synced))
      else: #elif pmt.to_long(pmt.car(msg))==0L
        array=pmt.to_python(msg)[1]
        self.numErrors[port]=array[12]
        self.numPackets[port]+=1
        if time.time()-self.printTime>2:#max every 2 sec
          print("errors:%s,Packets:%s, sync:%s"%(self.numErrors,self.numPackets,self.synced))
          self.printTime=time.time()
          self.numPackets=[0]*self.nPorts

