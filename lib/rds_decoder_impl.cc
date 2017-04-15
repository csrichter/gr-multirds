/* -*- c++ -*- */
/* 
 * Copyright 2016 <+YOU OR YOUR COMPANY+>.
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

#define dout debug && std::cout
#define lout log && std::cout

#include <gnuradio/io_signature.h>
#include "constants.h"
#include "rds_decoder_impl.h"
#include <map>
#include <vector>

namespace gr {
  namespace multirds {

    rds_decoder::sptr
    rds_decoder::make(bool log, bool debug)
    {
      return gnuradio::get_initial_sptr
        (new rds_decoder_impl(log, debug));
    }

    /*
     * The private constructor
     */
    rds_decoder_impl::rds_decoder_impl(bool log, bool debug)
      : gr::sync_block("rds_decoder",
              gr::io_signature::make (1, 1, sizeof(char)),
              gr::io_signature::make (0, 0, 0)),
	log(log),
	debug(debug)
{
	set_output_multiple(104);  // 1 RDS datagroup = 104 bits
	message_port_register_out(pmt::mp("out"));
	enter_no_sync();
        std::cout <<"i am old"<<std::endl;
}

    /*
     * Our virtual destructor.
     */
    rds_decoder_impl::~rds_decoder_impl()
    {
    }

////////////////////////// HELPER FUNTIONS /////////////////////////

void rds_decoder_impl::enter_no_sync() {
  	pmt::pmt_t data(pmt::PMT_F);
	//pmt::pmt_t meta(pmt::PMT_NIL);
	pmt::pmt_t meta(pmt::from_long(1));
	pmt::pmt_t pdu(pmt::cons(meta, data));  // make PDU: (metadata, data) pair
	message_port_pub(pmt::mp("out"), pdu);
	presync = false;
	d_state = NO_SYNC;
}

void rds_decoder_impl::enter_sync(unsigned int sync_block_number) {
  	pmt::pmt_t data(pmt::PMT_T);
	//pmt::pmt_t meta(pmt::PMT_NIL);
	pmt::pmt_t meta(pmt::from_long(1));
	pmt::pmt_t pdu(pmt::cons(meta, data));  // make PDU: (metadata, data) pair
	message_port_pub(pmt::mp("out"), pdu);
	last_wrong_blocks_counter = 0;
	wrong_blocks_counter   = 0;
	blocks_counter         = 0;
	block_bit_counter      = 0;
	block_number           = (sync_block_number + 1) % 4;
	group_assembly_started = false;
	d_state                = SYNC;
}

/* see Annex B, page 64 of the standard */
unsigned int rds_decoder_impl::calc_syndrome(unsigned long message,
		unsigned char mlen) {
	unsigned long reg = 0;
	unsigned int i;
	const unsigned long poly = 0x5B9;
	const unsigned char plen = 10;

	for (i = mlen; i > 0; i--)  {
		reg = (reg << 1) | ((message >> (i-1)) & 0x01);
		if (reg & (1 << plen)) reg = reg ^ poly;
	}
	for (i = plen; i > 0; i--) {
		reg = reg << 1;
		if (reg & (1<<plen)) reg = reg ^ poly;
	}
	return (reg & ((1<<plen)-1));	// select the bottom plen bits of reg
}

void rds_decoder_impl::decode_group(unsigned int *group) {
	// raw data bytes, as received from RDS.
	// 8 info bytes, followed by 4 RDS offset chars: ABCD/ABcD/EEEE (in US)
	unsigned char bytes[13];

	// RDS information words
	bytes[0] = (group[0] >> 8U) & 0xffU;
	bytes[1] = (group[0]      ) & 0xffU;
	bytes[2] = (group[1] >> 8U) & 0xffU;
	bytes[3] = (group[1]      ) & 0xffU;
	bytes[4] = (group[2] >> 8U) & 0xffU;
	bytes[5] = (group[2]      ) & 0xffU;
	bytes[6] = (group[3] >> 8U) & 0xffU;
	bytes[7] = (group[3]      ) & 0xffU;

	// RDS offset words
	bytes[8] = offset_chars[0];
	bytes[9] = offset_chars[1];
	bytes[10] = offset_chars[2];
	bytes[11] = offset_chars[3];
	bytes[12]=last_wrong_blocks_counter;
	pmt::pmt_t data(pmt::make_blob(bytes, 13));
	//pmt::pmt_t meta(pmt::PMT_NIL);
	pmt::pmt_t meta(pmt::from_long(0));
	pmt::pmt_t pdu(pmt::cons(meta, data));  // make PDU: (metadata, data) pair
	message_port_pub(pmt::mp("out"), pdu);
}
//work function
int rds_decoder_impl::work (int noutput_items,
		gr_vector_const_void_star &input_items,
		gr_vector_void_star &output_items)
{
	const bool *in = (const bool *) input_items[0];

	dout << "RDS data decoder at work: input_items = "
		<< noutput_items << ", /104 = "
		<< noutput_items / 104 << std::endl;

	int i=0,j;
	unsigned long bit_distance, block_distance;
	unsigned int block_calculated_crc, block_received_crc, checkword,dataword;
	unsigned int reg_syndrome;
	unsigned char offset_char('x');  // x = error while decoding the word offset

/* the synchronization process is described in Annex C, page 66 of the standard */
	while (i<noutput_items) {
		reg=(reg<<1)|in[i];		// reg contains the last 26 rds bits
		switch (d_state) {
			case NO_SYNC:
				reg_syndrome = calc_syndrome(reg,26);
				for (j=0;j<5;j++) {
					if (reg_syndrome==syndrome[j]) {
						if (!presync) {
							lastseen_offset=j;
							lastseen_offset_counter=bit_counter;
							presync=true;
						}
						else {
							bit_distance=bit_counter-lastseen_offset_counter;
							if (offset_pos[lastseen_offset]>=offset_pos[j]) 
								block_distance=offset_pos[j]+4-offset_pos[lastseen_offset];
							else
								block_distance=offset_pos[j]-offset_pos[lastseen_offset];
							if ((block_distance*26)!=bit_distance) presync=false;
							else {
								lout << "@@@@@ Sync State Detected" << std::endl;
								enter_sync(j);
							}
						}
					break; //syndrome found, no more cycles
					}
				}
			break;
			case SYNC:
/* wait until 26 bits enter the buffer */
				if (block_bit_counter<25) block_bit_counter++;
				else {
					good_block=false;
					dataword=(reg>>10) & 0xffff;//data part of received block (upper 16 bits)
					block_calculated_crc=calc_syndrome(dataword,16);
					checkword=reg & 0x3ff;//checkword part of received block (lower 10 bits)
/* manage special case of C or C' offset word */
					if (block_number==2) {
						block_received_crc=checkword^offset_word[block_number];
						if (block_received_crc==block_calculated_crc) {
							good_block=true;
							offset_char = 'C';
						} else {
							block_received_crc=checkword^offset_word[4];
							if (block_received_crc==block_calculated_crc) {
								good_block=true;
								offset_char = 'c';  // C' (C-Tag)
							} else {
								wrong_blocks_counter++;
								good_block=false;
							}
						}
					}
					else {
						block_received_crc=checkword^offset_word[block_number];
						if (block_received_crc==block_calculated_crc) {
							good_block=true;
							if (block_number==0) offset_char = 'A';
							else if (block_number==1) offset_char = 'B';
							else if (block_number==3) offset_char = 'D';
						} else {
							wrong_blocks_counter++;
							good_block=false;
						}
					}
/* done checking CRC */
					if (block_number==0 && good_block) {
						group_assembly_started=true;
						group_good_blocks_counter=1;
					}
					if (group_assembly_started) {
						if (!good_block) group_assembly_started=false;
						else {
							group[block_number]=dataword;
							offset_chars[block_number] = offset_char;
							group_good_blocks_counter++;
						}
						if (group_good_blocks_counter==5) decode_group(group);
					}
					block_bit_counter=0;
					block_number=(block_number+1) % 4;
					blocks_counter++;
/* 1187.5 bps / 104 bits = 11.4 groups/sec, or 45.7 blocks/sec */
					if (blocks_counter==50) {
						last_wrong_blocks_counter=wrong_blocks_counter;
						if (wrong_blocks_counter>35) {
							lout << "@@@@@ Lost Sync (Got " << wrong_blocks_counter
								<< " bad blocks on " << blocks_counter
								<< " total)" << std::endl;
							enter_no_sync();
						} else {
							lout << "@@@@@ Still Sync-ed (Got " << wrong_blocks_counter
								<< " bad blocks on " << blocks_counter
								<< " total)" << std::endl;
						}
						blocks_counter=0;
						wrong_blocks_counter=0;
					}
				}
			break;
			default:
				d_state=NO_SYNC;
			break;
		}
		i++;
		bit_counter++;
	}
	return noutput_items;
   }/*end of work function*/
   

  } /* namespace multirds */
} /* namespace gr */

