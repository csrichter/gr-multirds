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

#ifndef INCLUDED_MULTIRDS_STREAM_ROUTER_IMPL_H
#define INCLUDED_MULTIRDS_STREAM_ROUTER_IMPL_H

#include <multirds/stream_router.h>

namespace gr {
  namespace multirds {

    class stream_router_impl : public stream_router
    {
     private:
      // Nothing to declare in this block.

     public:
      stream_router_impl(int ninputs,int noutputs);
      ~stream_router_impl();

      // Where all the action really happens
      int work(int noutput_items,
         gr_vector_const_void_star &input_items,
         gr_vector_void_star &output_items);
    };

  } // namespace multirds
} // namespace gr

#endif /* INCLUDED_MULTIRDS_STREAM_ROUTER_IMPL_H */

