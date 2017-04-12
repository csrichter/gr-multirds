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
#include "sync_decim_impl.h"
#define DECIM 2
#define lout log && std::cout
#define SYNC_COUNTER_MAX 5//higher value -> slower sync, less cpu load
//#include <pmt.h>
namespace gr {
  namespace crfa {
    
    sync_decim::sptr
    sync_decim::make(float threshold,float min_diff,bool log)
    {
      return gnuradio::get_initial_sptr
      (new sync_decim_impl(threshold, min_diff, log));
    }
    
    /*
     * The private constructor
     */
    sync_decim_impl::sync_decim_impl(float threshold,float min_diff,bool log)
    : gr::sync_decimator("sync_decim",
        gr::io_signature::make(1, 1, sizeof(float)),
        gr::io_signature::make(1, 1, sizeof(float)), DECIM),
        threshold(threshold),
        min_diff(min_diff),
        log(log)
        
        {
          message_port_register_in(pmt::mp("ctrl"));
          set_msg_handler(pmt::mp("ctrl"), boost::bind(&sync_decim_impl::parse_ctrl_msg, this, _1));
          //init persistant vars
          last_input=0;
          mode=COPY;
	  dosync_counter=0;
        }
        /*
        * Our virtual destructor.
        */
        sync_decim_impl::~sync_decim_impl()
        {
        }
        
        void sync_decim_impl::parse_ctrl_msg(pmt::pmt_t pdu) {
          if(!pmt::is_pair(pdu)) {
          lout << "wrong input message (not a PDU)" << std::endl;
          return;
          }
          pmt::pmt_t meta = pmt::car(pdu);  // meta declares type 0:RDS, 1:sync/nosync
          pmt::pmt_t sync = pmt::cdr(pdu);
          if(1L==pmt::to_long(meta) && pmt::eqv(sync,pmt::PMT_F)){
            lout<< "entered nosync"<<std::endl;
            lout<<"mode: "<<mode<<std::endl;
            mode=COPY;
            lout<<"mode: "<<mode<<std::endl;
          }
        }
        
        
        int
        sync_decim_impl::work(int noutput_items,
                              gr_vector_const_void_star &input_items,
                              gr_vector_void_star &output_items)
        {
          const float *in = (const float *) input_items[0];
          float *out = (float *) output_items[0];
          
          for (int i = 0; i < noutput_items; i++) {
            if(mode==COPY){
              out[i]=in[DECIM*i];
            }
            else if(mode==SKIP){
              if(i==0){
                out[i]=last_input-in[DECIM*i];}
                else{
                  out[i]=in[DECIM*i-1]-in[DECIM*i];}
            }
            else if(mode==NOSKIP){
              out[i]=in[DECIM*i]-in[DECIM*i+1];
            }
          }
          last_input=in[(noutput_items-1)*DECIM+1];//to use for next iteration of work
          //lout<<noutput_items<<std::endl;
          
          /*synchronize:*/
          if(mode==COPY and dosync_counter==SYNC_COUNTER_MAX){
	    dosync_counter=0;
            float out_noskip;
            float out_skip;
            int skip_is_better_counter=0;
            if (noutput_items>8)//TODO: what if there are never more than 9 outputs requested
            {
              for (int i = 0; i < noutput_items; i++) {
                if(i==0){
                  out_skip=last_input-in[DECIM*i];}
                  else{
                    out_skip=in[DECIM*i-1]-in[DECIM*i];}
                    
                out_noskip=in[DECIM*i]-in[DECIM*i+1];
                if (std::abs(out_skip)>std::abs(out_noskip)){
		  skip_is_better_counter++;
                }
                else{
		  skip_is_better_counter--;
                }
                //lout<<"state:"<< mode;
                //lout<<"\t,out_noskip:"<<out_noskip;
                //lout<<"\t,out_skip:"<<out_skip<<std::endl;
                
              }
              if (skip_is_better_counter>6){
                mode=SKIP;
                lout<<"switched to skip"<< std::endl;
              }
              else if (skip_is_better_counter<-6){
                mode=NOSKIP;
                lout<<"switched to noskip"<< std::endl;
              }
            }
	    else if(mode==COPY){
	      dosync_counter++;
	      }
          }
          
          
          
          // Tell runtime system how many output items we produced.
          return noutput_items;
        }/*end of work*/
  } /* namespace crfa */
} /* namespace gr */

