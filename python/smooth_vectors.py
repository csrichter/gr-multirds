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

import numpy as np
from gnuradio import gr
import code

class smooth_vectors(gr.decim_block):
    """
    docstring for block smooth_vectors
    """
    def __init__(self, vec_len,decim,moving_avg_len):
        gr.decim_block.__init__(self,
            name="smooth_vectors",
            in_sig=[(np.float32,vec_len)],
            out_sig=[(np.float32,vec_len)], 
            decim=decim)
	self.vec_len=vec_len
	self.decim=decim
	self.moving_avg_len=moving_avg_len
	self.last_inputs=[]
	#self.count=1


    def work(self, input_items, output_items):
        in0 = input_items[0]#0th input port?
        out = output_items[0]
        #self.last_inputs.insert(0,in0)
        #code.interact(local=locals())
        for i in range(0,self.decim):
	  self.last_inputs.insert(0,in0[i])
        
        
        out[:] =np.mean( np.array(self.last_inputs), axis=0 )
        # <+signal processing here+>
        
        if len(self.last_inputs)>self.moving_avg_len:
	  self.last_inputs.pop(len(self.last_inputs)-1)#remove last
        #out[:] = in0
        #self.count += 1
        return len(output_items[0])

