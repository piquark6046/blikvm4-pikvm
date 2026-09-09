// SPDX-License-Identifier: GPL-2.0
/* M8-F0 ONLY. Observe bytes; never change capture state, contents or bytesused. */
#include <linux/debugfs.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/vmalloc.h>
#include <linux/unaligned.h>
#include "uvcvideo.h"

struct uvc_td_slot {
	struct uvc_td_event *event;
	struct uvc_td *owner;
	bool ready;
};
struct uvc_td {
	spinlock_t lock;
	struct uvc_td_packet packets[UVC_TD_RING];
	struct uvc_td_copy copies[UVC_TD_RING];
	u64 packets_seen, packets_written, copies_seen, frames_seen;
	u64 suspicious, admitted, acknowledged, suppressed, required_lost;
	u64 oversized, packet_overwrites, copy_overwrites;
	struct uvc_td_slot slots[UVC_TD_SLOTS];
};

static void edges(u8 *first, u8 *last, const u8 *p, size_t n)
{
	size_t k = min_t(size_t, n, 64);
	if (!k)
		return;
	memcpy(first, p, k);
	memcpy(last, p + n - k, k);
}

void uvc_td_begin(struct uvc_urb *u, int packet, int status,
		  unsigned int offset, unsigned int length, bool header)
{
	struct uvc_td *d = u->stream->taildiag;
	struct uvc_td_packet *p = &u->td_packet;
	const u8 *raw = u->urb->transfer_buffer + offset;
	unsigned long flags;
	unsigned int need, scr;

	if (!d)
		return;
	memset(p, 0, sizeof(*p));
	spin_lock_irqsave(&d->lock, flags);
	p->id = ++d->packets_seen;
	spin_unlock_irqrestore(&d->lock, flags);
	p->time_ns = ktime_get_ns();
	p->urb_index = uvc_urb_index(u);
	p->packet_index = packet;
	p->status = status;
	p->actual_length = length;
	p->transfer_offset = offset;
	p->header_present = header;
	p->decoded_header = -999;
	p->sequence = p->buffer_index = -1;
	p->copy_op_index = -1;
	p->bulk_header_size = u->stream->bulk.header_size;
	p->bulk_payload_size = u->stream->bulk.payload_size;
	p->bulk_max_payload_size = u->stream->bulk.max_payload_size;
	if (offset > u->urb->transfer_buffer_length ||
	    length > u->urb->transfer_buffer_length - offset) {
		p->status = -EOVERFLOW;
		p->actual_length = 0;
		return;
	}
	edges(p->raw_first, p->raw_last, raw, length);
	if (!header || length < 2)
		return;
	p->header_length = raw[0];
	p->header_flags = raw[1];
	p->fid = !!(raw[1] & UVC_STREAM_FID);
	p->eof = !!(raw[1] & UVC_STREAM_EOF);
	p->err = !!(raw[1] & UVC_STREAM_ERR);
	p->pts_present = !!(raw[1] & UVC_STREAM_PTS);
	p->scr_present = !!(raw[1] & UVC_STREAM_SCR);
	p->pts = p->scr_clock = p->scr_sof = -1;
	need = 2 + 4 * p->pts_present + 6 * p->scr_present;
	if (raw[0] < need || length < need)
		return;
	if (p->pts_present)
		p->pts = get_unaligned_le32(raw + 2);
	scr = 2 + 4 * p->pts_present;
	if (p->scr_present) {
		p->scr_clock = get_unaligned_le32(raw + scr);
		p->scr_sof = get_unaligned_le16(raw + scr + 4);
	}
}

void uvc_td_header(struct uvc_urb *u, struct uvc_buffer *b, int ret)
{
	struct uvc_td_packet *p = &u->td_packet;
	const u8 *raw;
	unsigned int off, count;
	if (!u->stream->taildiag)
		return;
	p->decoded_header = ret;
	if (b) {
		p->sequence = b->buf.sequence;
		p->buffer_index = b->buf.vb2_buf.index;
		p->before = p->after = b->bytesused;
		p->state_before = p->state_after = b->state;
	}
	if (ret < 0 || ret > p->actual_length)
		return;
	off = ret > 32 ? ret - 32 : 0;
	count = min_t(unsigned int, 64, p->actual_length - off);
	raw = u->urb->transfer_buffer + p->transfer_offset;
	p->boundary_offset = off;
	p->boundary_count = count;
	memcpy(p->boundary, raw + off, count);
}

void uvc_td_end(struct uvc_urb *u, struct uvc_buffer *b)
{
	struct uvc_td *d = u->stream->taildiag;
	struct uvc_td_packet *p = &u->td_packet;
	unsigned long flags;
	if (!d)
		return;
	if (b) {
		if (p->sequence < 0) {
			p->sequence = b->buf.sequence;
			p->buffer_index = b->buf.vb2_buf.index;
			p->before = b->bytesused;
		}
		p->after = b->bytesused;
		p->state_after = b->state;
	}
	spin_lock_irqsave(&d->lock, flags);
	if (d->packets_written >= UVC_TD_RING)
		d->packet_overwrites++;
	d->packets[d->packets_written++ % UVC_TD_RING] = *p;
	spin_unlock_irqrestore(&d->lock, flags);
}

void uvc_td_schedule(struct uvc_urb *u, struct uvc_copy_op *op)
{
	struct uvc_td_packet *p = &u->td_packet;
	if (!u->stream->taildiag)
		return;
	op->td_packet_id = p->id;
	p->sequence = op->buf->buf.sequence;
	p->buffer_index = op->buf->buf.vb2_buf.index;
	p->source_offset = op->src - (u8 *)u->urb->transfer_buffer;
	p->before = (u8 *)op->dst - (u8 *)op->buf->mem;
	p->after = p->before + op->len;
	p->copy_length = op->len;
	p->copy_op_index = u->async_operations;
	if (!p->before)
		op->buf->td_first_packet = p->id;
	edges(p->selected_first, p->selected_last, op->src, op->len);
}

void uvc_td_copy_before(struct uvc_urb *u, struct uvc_copy_op *op,
			unsigned int index, struct uvc_td_copy *c)
{
	if (!u->stream->taildiag)
		return;
	memset(c, 0, sizeof(*c));
	c->time_ns = ktime_get_ns();
	c->packet_id = op->td_packet_id;
	c->urb_index = uvc_urb_index(u);
	c->operation_index = index;
	c->sequence = op->buf->buf.sequence;
	c->buffer_index = op->buf->buf.vb2_buf.index;
	c->source_offset = op->src - (u8 *)u->urb->transfer_buffer;
	c->destination_offset = (u8 *)op->dst - (u8 *)op->buf->mem;
	c->length = op->len;
	edges(c->source_first, c->source_last, op->src, op->len);
}

void uvc_td_copy_after(struct uvc_urb *u, struct uvc_copy_op *op,
		       struct uvc_td_copy *c)
{
	struct uvc_td *d = u->stream->taildiag;
	unsigned long flags;
	if (!d)
		return;
	edges(c->destination_first, c->destination_last, op->dst, op->len);
	spin_lock_irqsave(&d->lock, flags);
	c->id = ++d->copies_seen;
	if (c->id > UVC_TD_RING)
		d->copy_overwrites++;
	d->copies[(c->id - 1) % UVC_TD_RING] = *c;
	spin_unlock_irqrestore(&d->lock, flags);
}

/* Structural marker walk skips APP/table payload and stuffed entropy. */
static bool structural_eoi(const u8 *p, size_t n)
{
	size_t i = 2, length;
	bool entropy = false;
	unsigned int m;
	if (n < 4 || p[0] != 255 || p[1] != 216)
		return false;
	while (i < n) {
		if (entropy && p[i] != 255) { ++i; continue; }
		if (p[i++] != 255) return false;
		while (i < n && p[i] == 255) ++i;
		if (i >= n) return false;
		m = p[i++];
		if (entropy && (!m || (m >= 208 && m <= 215))) continue;
		if (m == 217) return true;
		if (!m || m == 216 || (m >= 208 && m <= 215)) return false;
		if (m == 1) continue;
		if (n - i < 2) return false;
		length = (size_t)p[i] * 256 + p[i + 1];
		if (length < 2 || length > n - i) return false;
		i += length;
		entropy = m == 218;
	}
	return false;
}

void uvc_td_complete(struct uvc_streaming *s, struct uvc_buffer *b)
{
	struct uvc_td *d = s->taildiag;
	struct uvc_td_event *e;
	const u8 *data = b->mem;
	unsigned long flags;
	size_t end, n = b->bytesused;
	unsigned int slot, i, pc, cc;
	u64 oldest_copy_packet = U64_MAX;
	if (!d || !s->cur_format || s->cur_format->fcc != V4L2_PIX_FMT_MJPEG)
		return;
	spin_lock_irqsave(&d->lock, flags);
	d->frames_seen++;
	if (n > b->length || n > UVC_TD_FRAME) {
		d->oversized++;
		spin_unlock_irqrestore(&d->lock, flags);
		return;
	}
	spin_unlock_irqrestore(&d->lock, flags);
	for (end = n; end > 1; --end)
		if (data[end - 2] == 255 && data[end - 1] == 217) break;
	if (end <= 1 || end == n || !structural_eoi(data, n))
		return;
	spin_lock_irqsave(&d->lock, flags);
	d->suspicious++;
	for (slot = 0; slot < UVC_TD_SLOTS; ++slot)
		if (!d->slots[slot].ready) break;
	if (slot == UVC_TD_SLOTS) {
		d->suppressed++;
		spin_unlock_irqrestore(&d->lock, flags);
		return;
	}
	e = d->slots[slot].event;
	e->version = 1;
	e->id = ++d->admitted;
	e->time_ns = ktime_get_ns();
	e->sequence = b->buf.sequence;
	e->buffer_index = b->buf.vb2_buf.index;
	e->bytesused = n;
	e->buffer_error = b->error;
	e->final_eoi = end - 2;
	e->tail_length = n - end;
	e->first_packet = b->td_first_packet;
	pc = min_t(u64, UVC_TD_RING, d->packets_written);
	cc = min_t(u64, UVC_TD_RING, d->copies_seen);
	e->packet_count = pc;
	e->copy_count = cc;
	for (i = 0; i < pc; ++i)
		e->packets[i] = d->packets[(d->packets_written - pc + i) % UVC_TD_RING];
	for (i = 0; i < cc; ++i) {
		e->copies[i] = d->copies[(d->copies_seen - cc + i) % UVC_TD_RING];
		oldest_copy_packet = min_t(u64, oldest_copy_packet, e->copies[i].packet_id);
	}
	e->oldest_packet = pc ? e->packets[0].id : 0;
	e->newest_packet = pc ? e->packets[pc - 1].id : 0;
	e->required_lost = !e->first_packet || !pc || e->first_packet < e->oldest_packet ||
		!cc || e->first_packet < oldest_copy_packet;
	if (e->required_lost) d->required_lost++;
	/* Copies are finished: this hook runs at the final buffer kref release. */
	memcpy(e->frame, data, n);
	d->slots[slot].ready = true;
	spin_unlock_irqrestore(&d->lock, flags);
}

struct uvc_td_view {
	struct uvc_td_slot *slot;
	void *data;
	size_t size;
};
static int event_open(struct inode *inode, struct file *f)
{
	struct uvc_td_slot *slot = inode->i_private;
	struct uvc_td_view *v;
	unsigned long flags;
	u64 id = 0;
	v = kzalloc(sizeof(*v), GFP_KERNEL);
	if (!v) return -ENOMEM;
	v->slot = slot;
	spin_lock_irqsave(&slot->owner->lock, flags);
	if (slot->ready) {
		v->size = offsetof(struct uvc_td_event, frame) + slot->event->bytesused;
		id = slot->event->id;
	}
	spin_unlock_irqrestore(&slot->owner->lock, flags);
	if (v->size) {
		v->data = kvmalloc(v->size, GFP_KERNEL);
		if (!v->data) { kfree(v); return -ENOMEM; }
		spin_lock_irqsave(&slot->owner->lock, flags);
		if (!slot->ready || slot->event->id != id) v->size = 0;
		else memcpy(v->data, slot->event, v->size);
		spin_unlock_irqrestore(&slot->owner->lock, flags);
	}
	f->private_data = v;
	return 0;
}
static int event_release(struct inode *inode, struct file *f)
{
	struct uvc_td_view *v = f->private_data;
	kvfree(v->data);kfree(v);
	return 0;
}
static ssize_t event_read(struct file *f, char __user *buf, size_t n, loff_t *pos)
{
	struct uvc_td_view *v = f->private_data;
	return simple_read_from_buffer(buf, n, pos, v->data, v->size);
}
static ssize_t event_ack(struct file *f, const char __user *buf, size_t n, loff_t *pos)
{
	struct uvc_td_view *v = f->private_data;
	struct uvc_td_slot *slot = v->slot;
	struct uvc_td *d = slot->owner;
	unsigned long flags;
	u64 id;
	int ret = kstrtou64_from_user(buf, n, 10, &id);
	if (ret) return ret;
	spin_lock_irqsave(&d->lock, flags);
	if (!slot->ready || slot->event->id != id) ret = -ESTALE;
	else { slot->ready = false; d->acknowledged++; }
	spin_unlock_irqrestore(&d->lock, flags);
	return ret ? ret : n;
}
static const struct file_operations event_fops = {
	.owner = THIS_MODULE, .open = event_open, .read = event_read,
	.write = event_ack, .release = event_release, .llseek = default_llseek,
};
static ssize_t state_read(struct file *f, char __user *buf, size_t n, loff_t *pos)
{
	struct uvc_td *d = f->private_data;
	char text[1024];
	unsigned long flags;
	int len;
	spin_lock_irqsave(&d->lock, flags);
	len = scnprintf(text, sizeof(text),
		"version=1 packets_seen=%llu packets_written=%llu copies=%llu frames=%llu suspicious=%llu admitted=%llu acknowledged=%llu suppressed=%llu required_lost=%llu oversized=%llu packet_overwrites=%llu copy_overwrites=%llu memory_bytes=%zu packet_size=%zu copy_size=%zu event_header_size=%zu\n",
		d->packets_seen, d->packets_written, d->copies_seen, d->frames_seen,
		d->suspicious, d->admitted, d->acknowledged, d->suppressed,
		d->required_lost, d->oversized, d->packet_overwrites, d->copy_overwrites,
		sizeof(*d) + UVC_TD_SLOTS * sizeof(struct uvc_td_event),
		sizeof(struct uvc_td_packet), sizeof(struct uvc_td_copy),
		offsetof(struct uvc_td_event, packets));
	spin_unlock_irqrestore(&d->lock, flags);
	return simple_read_from_buffer(buf, n, pos, text, len);
}
static const struct file_operations state_fops = {
	.owner = THIS_MODULE, .open = simple_open, .read = state_read,
	.llseek = default_llseek,
};
void uvc_td_init(struct uvc_streaming *s)
{
	struct uvc_td *d;
	unsigned int i;
	char name[24];
	if (le16_to_cpu(s->dev->udev->descriptor.idVendor) != 0x345f ||
	    le16_to_cpu(s->dev->udev->descriptor.idProduct) != 0x2131 ||
	    s->type != V4L2_BUF_TYPE_VIDEO_CAPTURE || IS_ERR_OR_NULL(s->debugfs_dir))
		return;
	d = kvzalloc(sizeof(*d), GFP_KERNEL);
	if (!d) return;
	spin_lock_init(&d->lock);
	for (i = 0; i < UVC_TD_SLOTS; ++i) {
		d->slots[i].event = vzalloc(sizeof(struct uvc_td_event));
		if (!d->slots[i].event) goto fail;
		d->slots[i].owner = d;
	}
	s->taildiag = d;
	debugfs_create_file("taildiag-state", 0400, s->debugfs_dir, d, &state_fops);
	for (i = 0; i < UVC_TD_SLOTS; ++i) {
		snprintf(name, sizeof(name), "taildiag-event%u", i);
		debugfs_create_file(name, 0600, s->debugfs_dir, &d->slots[i], &event_fops);
	}
	return;
fail:
	for (i = 0; i < UVC_TD_SLOTS; ++i) vfree(d->slots[i].event);
	kvfree(d);
}
void uvc_td_cleanup(struct uvc_streaming *s)
{
	struct uvc_td *d = s->taildiag;
	unsigned int i;
	if (!d) return;
	for (i = 0; i < UVC_TD_SLOTS; ++i) vfree(d->slots[i].event);
	kvfree(d);
	s->taildiag = NULL;
}
