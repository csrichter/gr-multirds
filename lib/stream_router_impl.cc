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
#include "stream_router_impl.h"

namespace gr {
  namespace multirds {

    stream_router::sptr
    stream_router::make(int ninputs,int noutputs)
    {
      return gnuradio::get_initial_sptr
        (new stream_router_impl(ninputs, noutputs));
    }

    /*
     * The private constructor
     */
    stream_router_impl::stream_router_impl(int ninputs,int noutputs)
      : gr::sync_block("stream_router",
              gr::io_signature::make(3, 9, sizeof(float)),
              gr::io_signature::make(3, 3, sizeof(float)))
    {
        message_port_register_in(pmt::mp("ctrl"));
        set_msg_handler(pmt::mp("ctrl"), boost::bind(&stream_router_impl::parse_ctrl_msg, this, _1));
        //outmappings={0,1,2};
        outmappings[0]=0;
        outmappings[1]=1;
        outmappings[2]=2;
    }

    /*
     * Our virtual destructor.
     */
    stream_router_impl::~stream_router_impl()
    {
    }
    
    void stream_router_impl::parse_ctrl_msg(pmt::pmt_t pdu) {
          if(!pmt::is_pair(pdu)) {
          std::cout << "wrong input message (not a pair)" << std::endl;
          return;
          }
          pmt::pmt_t inport = pmt::car(pdu);  // meta declares type 0:RDS, 1:sync/nosync
          pmt::pmt_t outport = pmt::cdr(pdu);
          if(!pmt::is_integer(inport) or !pmt::is_integer(outport)) {
          std::cout << "wrong input message (not a long)" << std::endl;
          return;    
          }
          std::cout << pdu << std::endl;
          outmappings[pmt::to_long(outport)]=pmt::to_long(inport);
          //pmt::to_long(meta)
//           if(1L==pmt::to_long(meta) && pmt::eqv(sync,pmt::PMT_F)){
//             lout<< "entered nosync"<<std::endl;
//             lout<<"mode: "<<mode<<std::endl;
//             mode=COPY;
//             lout<<"mode: "<<mode<<std::endl;
//           }
        }
        
    int stream_router_impl::work(int noutput_items,
        gr_vector_const_void_star &input_items,
        gr_vector_void_star &output_items)
    {
//       const float *in0 = (const float *) input_items[0];
//       const float *in1 = (const float *) input_items[1];
//       const float *in2 = (const float *) input_items[2];
      const float *inports[] = {
          (const float *) input_items[0],(const float *) input_items[1],(const float *) input_items[2]
          ,(const float *) input_items[3],(const float *) input_items[4],(const float *) input_items[5]
          ,(const float *) input_items[6],(const float *) input_items[7],(const float *) input_items[8]
    };
      float *outs[] = {(float *) output_items[0],(float *) output_items[1],(float *) output_items[2]};
//       float *outL = (float *) output_items[0];
//       float *outC = (float *) output_items[1];
//       float *outR = (float *) output_items[2];  
      for (int i = 0; i < noutput_items; i++) {
          for (int outport=0;outport<3;outport++){
            outs[outport][i]=inports[outmappings[outport]][i];
          }
//       outL[i]=in0[i];
//       outC[i]=in1[i];
//       outR[i]=in2[i];  
      }
     

      // Do <+signal processing+>

      // Tell runtime system how many output items we produced.
      return noutput_items;
    }

  } /* namespace multirds */
} /* namespace gr */

