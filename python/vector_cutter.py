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
    def __init__(self, insize=2048,outsize=1024,cutpoint=512,pad_out=False):
	if pad_out:
	  gr.sync_block.__init__(self,
            name="vector_cutter",
            in_sig=[(np.complex64,insize)],
            out_sig=[(np.complex64,outsize),(np.complex64,insize)])
	else:
	  gr.sync_block.__init__(self,
            name="vector_cutter",
            in_sig=[(np.complex64,insize)],
            out_sig=[(np.complex64,outsize)])
	self.cutpoint=cutpoint
	self.insize=insize
	self.outsize=outsize
	print(pad_out)
	self.pad_out=pad_out

    def set_cutpoint(self, cutpoint=None):
     #print("cutpoint set to  %i"%cutpoint)
      if cutpoint is not None:
	      if isinstance(cutpoint, float) or isinstance(cutpoint, int):
		      self.cutpoint=cutpoint
	      else:
		      self.cutpoint = int(cutpoint)
    def work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        if self.pad_out:
	  out_padded = output_items[1]
        # <+signal processing here+>
        #out[:] = in0[512:1536]
        cutpoint=self.cutpoint
        attenuation=1e-2#40db (power)
	for i,in_vec in enumerate(in0):
	  if 0<=cutpoint<self.insize-self.outsize:
	    out[i]=in_vec[cutpoint:cutpoint+self.outsize]
	    if self.pad_out:
	      out_padded[i]=in_vec*np.concatenate((attenuation*np.ones(cutpoint),np.ones(self.outsize),attenuation*np.ones(self.insize-self.outsize-cutpoint)))
	  elif cutpoint <=self.insize:
	    out[i]=np.append(in_vec[cutpoint:self.insize],in_vec[0:self.outsize-self.insize+cutpoint])
	    if self.pad_out:
	      out_padded[i]=in_vec*np.concatenate((np.ones(cutpoint+self.outsize-self.insize),attenuation*np.ones(self.insize-self.outsize),np.ones(self.insize-cutpoint)))
	  #out[i]=np.append(out_cut[self.outsize/2:self.outsize],out_cut[0:self.outsize/2])
	#out = in0[512:1536]
        #code.interact(local=locals())
        #out[0] = in0[0][512:1536]
        #out[1] = in0[1][512:1536]
        return len(output_items[0])

