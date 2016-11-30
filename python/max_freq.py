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

class max_freq(gr.sync_block):
    """
    docstring for block max_freq
    """
    def __init__(self, fft_len=1024,num_decoders=4,center_freq=0,samp_rate=0):
        gr.sync_block.__init__(self,
            name="max_freq",
            in_sig=[(np.float32,fft_len)],
            out_sig=None)
        self.fft_len=fft_len
        self.num_decoders=num_decoders
        self.center_freq=center_freq
        self.samp_rate=samp_rate
        self.num_averages=5
        self.avg_counter=-1
        self.numbers_avg=[]


    def work(self, input_items, output_items):
      #in0 = input_items[0]
      #ii=input_items
      numbers=abs(input_items[0][0])
      threshold=6
      if self.avg_counter == -1: #init
        self.numbers_avg=numbers
        self.avg_counter=0
      elif self.avg_counter <= self.num_averages:
        #np.mean( np.array([ old_set, new_set ]), axis=0 )
        self.numbers_avg=np.mean( np.array([ self.numbers_avg, numbers ]), axis=0 )
        self.avg_counter+=1
      elif len(np.where(self.numbers_avg>threshold)[0]) >0:
        self.avg_counter=0
        numbers=self.numbers_avg
        min_consec_max_threshold=4#minimum number of consecutive maximums (in fft domain) to consider signal as station
        #TODO: what if no numbers over threshold?
        #TODO auto threshold
        #max_indices=[[421, 428, 429, 430, 431, 432, 433, 434, 436, 437, 438, 831, 832, 837, 840, 841, 842, 843, 844, 845, 846, 847, 848, 849, 850, 851,852, 853, 854, 855, 856, 857]]
        max_indices=np.where(numbers>threshold)
        station_indices=[]
        
        last_index=max_indices[0][0]
        #last_index=0
        count=1#counts number of consecutive maximums
        threshold_reached=False
        fuzzyness=10
#        max_indices[0].append(0)#to detect last station
        max_indices=np.append(max_indices,0)#to detect last station
        for i in max_indices:
          if abs(i-last_index) <= fuzzyness:
            count+=i-last_index
          else:#last streak ended
            if(threshold_reached):
              station_indices.append(last_index-int(count/2))#use center of max-streak
              threshold_reached=False
              count=1
            else:#last streak didn't reach threshold -> no station
              count=1
          if count==min_consec_max_threshold:
            threshold_reached=True
          last_index=i
          
        station_freqs=[]
        #index to freq:
        for index in station_indices:
          startfreq=self.center_freq-self.samp_rate/2
          freq=self.samp_rate*index/self.fft_len+startfreq
          station_freqs.append(freq)
        
        """
[422 423 426 427 428 430 431 432 433 434 435 436 437 836 837 838 842 843
 844 845 846 847 848 849 850 851 852 853 854 855 856 857 858 859 861 862
   0]
[]
[]
[423 424 425 426 427 428 429 430 431 432 433 434 842 843 844 845 848 849
 850 851 852 853 854 855 858 859 860   0]
[428, 851]
[101303125.0, 102294531.0]
[415 416 419 420 421 422 423 424 425 426 427 428 429 430 431 432 433 434
 844 845 846 847 848 849 850 851 852 853 854 855 856 861 862 863   0]
[853]
[102299218.0]
"""
        #f=open("/tmp/obj","r")
        #import pickle
        #pickle.load(ii,f)
        #(array([431, 433, 437, 439, 849, 854, 856, 858, 861, 862]),)
        #code.interact(local=locals())
        # <+signal processing here+>
        print(max_indices)
        print(station_indices)
        print(station_freqs)
      return len(input_items[0])

