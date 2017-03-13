/* -*- c++ -*- */
/* 
 * Copyright 2017 <+YOU OR YOUR COMPANY+>.
 * 
 * This is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * This software is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this software; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gnuradio/io_signature.h>
#include "diff_add_sync_decim_impl.h"
#define DECIM 2
#define lout log && std::cout

namespace gr {
  namespace crfa {

    diff_add_sync_decim::sptr
    diff_add_sync_decim::make(float threshold,float max_ratio_below_threshold,bool log)
    {
      return gnuradio::get_initial_sptr
        (new diff_add_sync_decim_impl(threshold,max_ratio_below_threshold,log));
    }

    /*
     * The private constructor
     */
    diff_add_sync_decim_impl::diff_add_sync_decim_impl(float threshold,float max_ratio_below_threshold,bool log)
      : gr::sync_decimator("diff_add_sync_decim",
              gr::io_signature::make(1, 1, sizeof(float)),
              gr::io_signature::make(1, 1, sizeof(float)), DECIM),
              threshold(threshold),
              max_ratio_below_threshold(max_ratio_below_threshold),
              log(log)
              
    {
      //nothing to do?
      
      //init persistant vars
      last_input=0;
      skip=0;
    }

    /*
     * Our virtual destructor.
     */
    diff_add_sync_decim_impl::~diff_add_sync_decim_impl()
    {
    }

    int
    diff_add_sync_decim_impl::work(int noutput_items,
        gr_vector_const_void_star &input_items,
        gr_vector_void_star &output_items)
    {

      const float *in = (const float *) input_items[0];
      float *out = (float *) output_items[0];
      int values_below_threshold=0;
      int values_below_threshold_skip=0;
      int values_below_threshold_noskip=0;
      float out_noskip;
      float out_skip;
      for (int i = 0; i < noutput_items; i++) {
        //out[i]=in[DECIM*i];// keep 1 in DECIM
        if(i==0){
            out_skip=last_input-in[DECIM*i];}
        else{
            out_skip=in[DECIM*i-1]-in[DECIM*i];}
            
        out_noskip=in[DECIM*i]-in[DECIM*i+1];
        
        switch(skip){
          case 0:
            out[i]=out_noskip;
            break;
          case 1:
            out[i]=out_skip;
            break;
          default:
            out[i]=out_noskip;
            break;
        }
        
        if(abs(out[i])<threshold){
          values_below_threshold++;
        }
        
        if(abs(out_noskip)<threshold){
          values_below_threshold_noskip++;
        }       
        
        if(abs(out_skip)<threshold){
          values_below_threshold_skip++;
        }
      }
      last_input=in[(noutput_items-1)*DECIM+1];//to use for next iteration of work
      //if ((float)values_below_threshold / (float)noutput_items >0.5)
      if ((float)values_below_threshold / (float)noutput_items >max_ratio_below_threshold && values_below_threshold>8)//2/2(=100%) below threshold is not significant
      {
        //lout<<"resync:"<<values_below_threshold<<"/"<<noutput_items<<", skip:"<<skip<<", last_input:"<<last_input<<std::endl;
        lout<<"out_skip:"<<values_below_threshold_skip<<"/"<<noutput_items;
        lout<<", out_noskip:"<<values_below_threshold_noskip<<"/"<<noutput_items;
        lout<<", skip:"<<skip <<std::endl;
        switch(skip){
          case 0:skip=1;break;
          case 1:skip=0;break;
          default:skip=0;break;
        }
      }
//       if(noutput_items>9){
//         if(values_below_threshold_noskip>values_below_threshold_skip){
//           skip=1;
//         }
//         else{
//           skip=0;
//         }
//       }
      //lout << "noutput_items:"<< noutput_items <<", threshold:"<<threshold << std::endl;
      //lout << "out[0]:"<< out[0] <<", threshold:"<<threshold << std::endl;
      // Tell runtime system how many output items we produced.
      return noutput_items;
    }

  } /* namespace crfa */
} /* namespace gr */

