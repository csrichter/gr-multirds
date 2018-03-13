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

import numpy as np
from gnuradio import gr
import pmt,time,functools
class RingBuffer():
    "A 1D ring buffer using numpy arrays"
    def __init__(self, length):
        self.data = np.zeros(length, dtype='f')
        self.index = 0
    def extend(self, x):
        "adds array x to ring buffer"
        x_index = (self.index + np.arange(x.size)) % self.data.size
        self.data[x_index] = x
        self.index = x_index[-1] + 1
    def get(self):
        "Returns the first-in-first-out data in the ring buffer"
        idx = (self.index + np.arange(self.data.size)) %self.data.size
        return self.data[idx]
class stream_selector(gr.sync_block):
    """
    docstring for block stream_selector
    """
    def __init__(self):
        gr.sync_block.__init__(self,
            name="stream_selector",
            in_sig=[np.float32,np.float32],
            out_sig=None
            )
	#self.repeat_time=repeat_time
	self.repeat_time=1
	moving_avg_len=50
	self.message_port_register_out(pmt.intern('rds_out'))
	self.message_port_register_in(pmt.intern('rds_arg'))
	self.set_msg_handler(pmt.intern('rds_arg'), functools.partial(self.handle_msg, port="arg"))
	self.message_port_register_in(pmt.intern('rds_re'))
	self.set_msg_handler(pmt.intern('rds_re'), functools.partial(self.handle_msg, port="re"))
	
	#self.port_of_recent_messages=RingBuffer(10)#change to more fitting ringbuffer for ints
	self.port_of_recent_messages=0#re as default
	self.real_abs=RingBuffer(moving_avg_len)
	self.arg_diff_abs=RingBuffer(moving_avg_len)
	self.msg_time=time.time()
    def handle_msg(self,msg,port):
      msg_py=pmt.to_python(msg)
      if port=="re":
	#self.port_of_recent_messages.extend(np.array([0],dtype='f'))
	self.port_of_recent_messages=(self.port_of_recent_messages*19+0)/20
      if port=="arg":
	self.port_of_recent_messages=(self.port_of_recent_messages*19+100)/20
	#self.port_of_recent_messages.extend(np.array([100],dtype='f'))
      #print(np.average(self.port_of_recent_messages.get()))
      print(self.port_of_recent_messages)
      print("msg: %s, port:%s"%(msg_py,port))
      
    def work(self, input_items, output_items):
        self.real_abs.extend(np.absolute(input_items[0]))
        self.arg_diff_abs.extend(np.absolute(input_items[1]))
        
        if(time.time()-self.msg_time > self.repeat_time):
	  self.msg_time=time.time()
	  #print("real: ")
	  ##print(real_abs)
	  #print(np.average(self.real_abs.get()))
	  #print("arg: ")
	  ##print(arg_diff_abs)
	  #print(np.average(self.arg_diff_abs.get()))
        return len(input_items[0])
