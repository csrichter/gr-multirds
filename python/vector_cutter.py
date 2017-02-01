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
import code

class vector_cutter(gr.sync_block):
    """
    docstring for block vector_cutter
    """
    def __init__(self, insize=2048,outsize=1024,cutpoint=512):
        gr.sync_block.__init__(self,
            name="vector_cutter",
            in_sig=[(np.complex64,insize)],
            out_sig=[(np.complex64,outsize)])
	    
	self.cutpoint=cutpoint
	self.insize=insize
	self.outsize=outsize

    def set_cutpoint(self, cutpoint=None):
      print("cutpoint set to  %i"%cutpoint)
      if cutpoint is not None:
	      if isinstance(cutpoint, float) or isinstance(cutpoint, int):
		      self.cutpoint=cutpoint
	      else:
		      self.cutpoint = int(cutpoint)
    def work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        # <+signal processing here+>
        #out[:] = in0[512:1536]
	for i,in_vec in enumerate(in0):
	  out[i]=in_vec[self.cutpoint:self.cutpoint+self.outsize]
	#out = in0[512:1536]
        #code.interact(local=locals())
        #out[0] = in0[0][512:1536]
        #out[1] = in0[1][512:1536]
        return len(output_items[0])

