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
import pmt,time


class pilot_quality(gr.sync_block):
    """
    docstring for block pilot_quality
    """
    def __init__(self, debug,samp_rate,fft_len,carrier_freq,gap_width,msg_adr):
        gr.sync_block.__init__(self,
            name="pilot_quality",
            in_sig=[(np.float32,fft_len)],
            out_sig=None)
        #self.carrier_width=1
        self.debug=debug
        self.msg_adr=msg_adr
        self.message_port_register_out(pmt.intern('out'))
        self.carrier_index=int(carrier_freq*fft_len/float(samp_rate))
        self.lowbound_index=int((carrier_freq-gap_width)*fft_len/float(samp_rate))
        self.highbound_index=int((carrier_freq+gap_width)*fft_len/float(samp_rate))
        self.send_timer=time.time()
        self.strength_list=[]
    def work(self, input_items, output_items):
        in0 = input_items[0]
        # <+signal processing here+>
        for i,in_vec in enumerate(in0):
            surrounding=np.mean(in_vec[self.lowbound_index:self.highbound_index])
            carrier=np.mean(in_vec[self.carrier_index-1:self.carrier_index+1])
            #code.interact(local=locals())
            strength=abs(carrier-surrounding)
            self.strength_list.append(strength)
            #if self.debug:
            #    print("i:%i,strength: %f,carrier: %f, around:%f"%(i,strength,carrier,surrounding))
        if time.time()-self.send_timer>0.1:#10 times per second
            self.send_timer=time.time()
            strength_mean=int(np.mean(self.strength_list))
            self.strength_list=[]
            send_pmt = pmt.cons(pmt.from_long(self.msg_adr),pmt.from_long(strength_mean))
            self.message_port_pub(pmt.intern('out'), send_pmt)
            if self.debug:
                print("mean:%i"%strength_mean)
        return len(input_items[0])

