#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2016 <+YOU OR YOUR COMPANY+>.
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

import numpy,pmt,functools
from gnuradio import gr

class multi_rds_printer(gr.sync_block):
    """
    docstring for block multi_rds_printer
    """
    def __init__(self, print_freq,nPorts):
	gr.sync_block.__init__(self,
	  name="multi_rds_printer",
	  in_sig=None,
	  out_sig=None)
	self.PS="station name"
	self.RT="radio text"
	self.PI="C0FE"
	self.stations = {}
	self.print_freq = print_freq
	self.print_count=print_freq
	for i in range(0,nPorts):
	  self.message_port_register_in(pmt.intern('in%d'%i))
	  self.set_msg_handler(pmt.intern('in%d'%i), functools.partial(self.handle_msg, port=i))
    def handle_msg(self, msg, port):
	t = pmt.to_long(pmt.tuple_ref(msg, 0))
	m = pmt.symbol_to_string(pmt.tuple_ref(msg, 1))
	#code.interact(local=locals())
	if(t==0):
		self.PI=m
		self.stations[str(port)+"PI"]=m
	elif(t==1):
		self.PS=m
		self.stations[str(port)+"PS"]=m
	elif(t==4):
		self.RT=m
		self.stations[str(port)+"RT"]=m
	self.print_count -= 1
	#print(self.stations)
	if (self.print_count==0):
		self.print_count=self.print_freq
		print("########## stations ###########")
		for key in sorted(self.stations):
		    print("%s: %s" % (key, self.stations[key]))
#    def work(self, input_items, output_items):
#        in0 = input_items[0]
#        out = output_items[0]
#        # <+signal processing here+>
#        out[:] = in0
#        return len(output_items[0])

