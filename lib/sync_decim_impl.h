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

#ifndef INCLUDED_CRFA_SYNC_DECIM_IMPL_H
#define INCLUDED_CRFA_SYNC_DECIM_IMPL_H

#include <crfa/sync_decim.h>

namespace gr {
  namespace crfa {

    class sync_decim_impl : public sync_decim
    {
     private:
      // Nothing to declare in this block.

     public:
      sync_decim_impl(float threshold,float min_diff,bool log);
      ~sync_decim_impl();

      // Where all the action really happens
      int work(int noutput_items,
         gr_vector_const_void_star &input_items,
         gr_vector_void_star &output_items);
      bool  log;
      float threshold;
      float min_diff;
      float last_input;
      enum {COPY, SKIP, NOSKIP } mode;
      unsigned int skip;
      void parse_ctrl_msg(pmt::pmt_t pdu);
    };

  } // namespace crfa
} // namespace gr

#endif /* INCLUDED_CRFA_SYNC_DECIM_IMPL_H */

