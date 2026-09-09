/* SPDX-License-Identifier: GPL-2.0 */
/* M8-F0 diagnostic-only ABI, little endian 64-bit scalar fields. */
#ifndef _UVC_TAILDIAG_H
#define _UVC_TAILDIAG_H
#include <linux/types.h>
#define UVC_TD_RING 512
#define UVC_TD_FRAME (4U * 1024U * 1024U)
#define UVC_TD_SLOTS 8
struct uvc_td_packet {
	s64 id;
	s64 time_ns;
	s64 urb_index;
	s64 packet_index;
	s64 status;
	s64 actual_length;
	s64 transfer_offset;
	s64 header_present;
	s64 decoded_header;
	s64 sequence;
	s64 buffer_index;
	s64 before;
	s64 after;
	s64 source_offset;
	s64 copy_length;
	s64 header_length;
	s64 header_flags;
	s64 fid;
	s64 eof;
	s64 err;
	s64 pts_present;
	s64 pts;
	s64 scr_present;
	s64 scr_clock;
	s64 scr_sof;
	s64 boundary_offset;
	s64 boundary_count;
	s64 copy_op_index;
	s64 bulk_header_size;
	s64 bulk_payload_size;
	s64 bulk_max_payload_size;
	s64 state_before;
	s64 state_after;
	u8 raw_first[64];
	u8 raw_last[64];
	u8 boundary[64];
	u8 selected_first[64];
	u8 selected_last[64];
};
struct uvc_td_copy {
	s64 id;
	s64 time_ns;
	s64 packet_id;
	s64 urb_index;
	s64 operation_index;
	s64 sequence;
	s64 buffer_index;
	s64 source_offset;
	s64 destination_offset;
	s64 length;
	u8 source_first[64];
	u8 source_last[64];
	u8 destination_first[64];
	u8 destination_last[64];
};
struct uvc_td_event {
	s64 version;
	s64 id;
	s64 time_ns;
	s64 sequence;
	s64 buffer_index;
	s64 bytesused;
	s64 buffer_error;
	s64 final_eoi;
	s64 tail_length;
	s64 first_packet;
	s64 oldest_packet;
	s64 newest_packet;
	s64 packet_count;
	s64 copy_count;
	s64 required_lost;
	s64 reserved;
	struct uvc_td_packet packets[UVC_TD_RING];
	struct uvc_td_copy copies[UVC_TD_RING];
	u8 frame[UVC_TD_FRAME];
};
struct uvc_td;
struct uvc_streaming;
struct uvc_urb;
struct uvc_buffer;
struct uvc_copy_op;
void uvc_td_init(struct uvc_streaming *s);
void uvc_td_cleanup(struct uvc_streaming *s);
void uvc_td_begin(struct uvc_urb *u, int packet, int status, unsigned int offset, unsigned int length, bool header);
void uvc_td_header(struct uvc_urb *u, struct uvc_buffer *b, int ret);
void uvc_td_end(struct uvc_urb *u, struct uvc_buffer *b);
void uvc_td_schedule(struct uvc_urb *u, struct uvc_copy_op *op);
void uvc_td_copy_before(struct uvc_urb *u, struct uvc_copy_op *op, unsigned int index, struct uvc_td_copy *c);
void uvc_td_copy_after(struct uvc_urb *u, struct uvc_copy_op *op, struct uvc_td_copy *c);
void uvc_td_complete(struct uvc_streaming *s, struct uvc_buffer *b);
#endif
