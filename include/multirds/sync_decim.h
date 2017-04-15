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


#ifndef INCLUDED_CRFA_SYNC_DECIM_H
#define INCLUDED_CRFA_SYNC_DECIM_H

#include <multirds/api.h>
#include <gnuradio/sync_decimator.h>

namespace gr {
  namespace multirds {

    /*!
     * \brief <+description of block+>
     * \ingroup multirds
     *
     */
    class CRFA_API sync_decim : virtual public gr::sync_decimator
    {
     public:
      typedef boost::shared_ptr<sync_decim> sptr;

      /*!
       * \brief Return a shared_ptr to a new instance of multirds::sync_decim.
       *
       * To avoid accidental use of raw pointers, multirds::sync_decim's
       * constructor is in a private implementation
       * class. multirds::sync_decim::make is the public interface for
       * creating new instances.
       */
      static sptr make(float threshold,float min_diff,bool log);
    };

  } // namespace multirds
} // namespace gr

#endif /* INCLUDED_CRFA_SYNC_DECIM_H */

