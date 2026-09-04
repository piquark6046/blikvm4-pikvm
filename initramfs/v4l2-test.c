// SPDX-License-Identifier: GPL-2.0-only
/* Minimal, dependency-free V4L2 enumeration and bounded capture utility. */

#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#define MAX_VIDEO_NODES 64
#define MAX_CAPTURE_FRAMES 120

struct mapped_buffer {
	void *address;
	size_t length;
};

static int xioctl(int fd, unsigned long request, void *argument)
{
	int result;

	do {
		result = ioctl(fd, request, argument);
	} while (result < 0 && errno == EINTR);
	return result;
}

static const char *safe_text(const unsigned char *source, char *destination,
			     size_t size)
{
	size_t index;

	if (size == 0)
		return destination;
	for (index = 0; index + 1 < size && source[index] != '\0'; ++index) {
		unsigned char value = source[index];

		destination[index] = value > 0x20 && value < 0x7f ? (char)value : '_';
	}
	destination[index] = '\0';
	return destination;
}

static const char *fourcc_text(uint32_t value, char result[5])
{
	unsigned int index;

	for (index = 0; index < 4; ++index) {
		unsigned char byte = (value >> (index * 8)) & 0xff;

		result[index] = byte > 0x20 && byte < 0x7f ? (char)byte : '.';
	}
	result[4] = '\0';
	return result;
}

static uint32_t parse_fourcc(const char *text)
{
	if (strlen(text) != 4) {
		fprintf(stderr, "fourcc must contain exactly four characters: %s\n", text);
		exit(2);
	}
	return v4l2_fourcc(text[0], text[1], text[2], text[3]);
}

static unsigned int parse_unsigned(const char *name, const char *text,
				   unsigned int minimum,
				   unsigned int maximum)
{
	char *end = NULL;
	unsigned long value;

	errno = 0;
	value = strtoul(text, &end, 10);
	if (errno != 0 || end == text || *end != '\0' || value < minimum ||
	    value > maximum) {
		fprintf(stderr, "invalid %s: %s\n", name, text);
		exit(2);
	}
	return (unsigned int)value;
}

static uint32_t effective_capabilities(const struct v4l2_capability *capability)
{
	if (capability->capabilities & V4L2_CAP_DEVICE_CAPS)
		return capability->device_caps;
	return capability->capabilities;
}

static void print_interval(const char *device, uint32_t pixel_format,
			   unsigned int width, unsigned int height,
			   const struct v4l2_frmivalenum *interval)
{
	char fourcc[5];

	if (interval->type == V4L2_FRMIVAL_TYPE_DISCRETE) {
		double fps = interval->discrete.numerator == 0 ? 0.0 :
			(double)interval->discrete.denominator /
			(double)interval->discrete.numerator;

		printf("INTERVAL device=%s fourcc=%s width=%u height=%u index=%u "
		       "kind=discrete numerator=%u denominator=%u fps=%.3f\n",
		       device, fourcc_text(pixel_format, fourcc), width, height,
		       interval->index, interval->discrete.numerator,
		       interval->discrete.denominator, fps);
	} else {
		const struct v4l2_fract *minimum = &interval->stepwise.min;
		const struct v4l2_fract *maximum = &interval->stepwise.max;
		const struct v4l2_fract *step = &interval->stepwise.step;
		const char *kind = interval->type == V4L2_FRMIVAL_TYPE_CONTINUOUS ?
			"continuous" : "stepwise";

		printf("INTERVAL device=%s fourcc=%s width=%u height=%u index=%u "
		       "kind=%s min=%u/%u max=%u/%u step=%u/%u\n",
		       device, fourcc_text(pixel_format, fourcc), width, height,
		       interval->index, kind, minimum->numerator,
		       minimum->denominator, maximum->numerator,
		       maximum->denominator, step->numerator, step->denominator);
	}
}

static unsigned int enumerate_intervals(int fd, const char *device,
					uint32_t pixel_format,
					unsigned int width,
					unsigned int height)
{
	struct v4l2_frmivalenum interval;
	unsigned int count = 0;

	memset(&interval, 0, sizeof(interval));
	interval.pixel_format = pixel_format;
	interval.width = width;
	interval.height = height;
	for (interval.index = 0; ; ++interval.index) {
		if (xioctl(fd, VIDIOC_ENUM_FRAMEINTERVALS, &interval) < 0) {
			if (errno != EINVAL)
				fprintf(stderr, "ENUM_INTERVAL_ERROR device=%s errno=%d\n",
					device, errno);
			break;
		}
		print_interval(device, pixel_format, width, height, &interval);
		++count;
		if (interval.type != V4L2_FRMIVAL_TYPE_DISCRETE)
			break;
	}
	return count;
}

static unsigned int enumerate_sizes(int fd, const char *device,
				    uint32_t pixel_format,
				    unsigned int *interval_count)
{
	struct v4l2_frmsizeenum size;
	unsigned int count = 0;
	char fourcc[5];

	memset(&size, 0, sizeof(size));
	size.pixel_format = pixel_format;
	for (size.index = 0; ; ++size.index) {
		if (xioctl(fd, VIDIOC_ENUM_FRAMESIZES, &size) < 0) {
			if (errno != EINVAL)
				fprintf(stderr, "ENUM_SIZE_ERROR device=%s errno=%d\n",
					device, errno);
			break;
		}
		++count;
		if (size.type == V4L2_FRMSIZE_TYPE_DISCRETE) {
			printf("SIZE device=%s fourcc=%s index=%u kind=discrete "
			       "width=%u height=%u\n", device,
			       fourcc_text(pixel_format, fourcc), size.index,
			       size.discrete.width, size.discrete.height);
			*interval_count += enumerate_intervals(fd, device, pixel_format,
							 size.discrete.width,
							 size.discrete.height);
		} else {
			const char *kind = size.type == V4L2_FRMSIZE_TYPE_CONTINUOUS ?
				"continuous" : "stepwise";

			printf("SIZE device=%s fourcc=%s index=%u kind=%s "
			       "min_width=%u max_width=%u step_width=%u "
			       "min_height=%u max_height=%u step_height=%u\n",
			       device, fourcc_text(pixel_format, fourcc), size.index,
			       kind, size.stepwise.min_width, size.stepwise.max_width,
			       size.stepwise.step_width, size.stepwise.min_height,
			       size.stepwise.max_height, size.stepwise.step_height);
			*interval_count += enumerate_intervals(fd, device, pixel_format,
							 size.stepwise.min_width,
							 size.stepwise.min_height);
			break;
		}
	}
	return count;
}

static unsigned int enumerate_formats(int fd, const char *device,
				      enum v4l2_buf_type type,
				      unsigned int *size_count,
				      unsigned int *interval_count)
{
	struct v4l2_fmtdesc format;
	unsigned int count = 0;
	char description[128];
	char fourcc[5];
	const char *type_name = type == V4L2_BUF_TYPE_VIDEO_CAPTURE ?
		"video_capture" : "metadata_capture";

	memset(&format, 0, sizeof(format));
	format.type = type;
	for (format.index = 0; ; ++format.index) {
		if (xioctl(fd, VIDIOC_ENUM_FMT, &format) < 0) {
			if (errno != EINVAL)
				fprintf(stderr, "ENUM_FORMAT_ERROR device=%s errno=%d\n",
					device, errno);
			break;
		}
		printf("FORMAT device=%s type=%s index=%u fourcc=%s flags=0x%08x "
		       "description=%s\n", device, type_name, format.index,
		       fourcc_text(format.pixelformat, fourcc), format.flags,
		       safe_text(format.description, description, sizeof(description)));
		++count;
		if (type == V4L2_BUF_TYPE_VIDEO_CAPTURE)
			*size_count += enumerate_sizes(fd, device, format.pixelformat,
						      interval_count);
	}
	return count;
}

static unsigned int enumerate_inputs(int fd, const char *device)
{
	struct v4l2_input input;
	int current = -1;
	unsigned int count = 0;
	char name[128];

	(void)xioctl(fd, VIDIOC_G_INPUT, &current);
	memset(&input, 0, sizeof(input));
	for (input.index = 0; ; ++input.index) {
		if (xioctl(fd, VIDIOC_ENUMINPUT, &input) < 0) {
			if (errno != EINVAL && errno != ENOTTY)
				fprintf(stderr, "ENUM_INPUT_ERROR device=%s errno=%d\n",
					device, errno);
			break;
		}
		printf("INPUT device=%s index=%u current=%u name=%s type=%u "
		       "status=0x%08x capabilities=0x%08x std=0x%016" PRIx64 "\n",
		       device, input.index, current >= 0 && (unsigned int)current == input.index,
		       safe_text(input.name, name, sizeof(name)), input.type, input.status,
		       input.capabilities, (uint64_t)input.std);
		++count;
	}
	return count;
}

static unsigned int enumerate_standards(int fd, const char *device)
{
	struct v4l2_standard standard;
	unsigned int count = 0;
	char name[128];

	memset(&standard, 0, sizeof(standard));
	for (standard.index = 0; ; ++standard.index) {
		if (xioctl(fd, VIDIOC_ENUMSTD, &standard) < 0) {
			if (errno != EINVAL && errno != ENOTTY)
				fprintf(stderr, "ENUM_STANDARD_ERROR device=%s errno=%d\n",
					device, errno);
			break;
		}
		printf("STANDARD device=%s index=%u id=0x%016" PRIx64 " name=%s "
		       "frameperiod=%u/%u framelines=%u\n", device, standard.index,
		       (uint64_t)standard.id,
		       safe_text(standard.name, name, sizeof(name)),
		       standard.frameperiod.numerator, standard.frameperiod.denominator,
		       standard.framelines);
		++count;
	}
	if (count == 0)
		printf("STANDARDS device=%s applicable=0 count=0\n", device);
	return count;
}

static void print_current_video_format(int fd, const char *device)
{
	struct v4l2_format format;
	struct v4l2_streamparm parameters;
	char fourcc[5];

	memset(&format, 0, sizeof(format));
	format.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
	if (xioctl(fd, VIDIOC_G_FMT, &format) == 0) {
		printf("CURRENT_FORMAT device=%s type=video_capture fourcc=%s width=%u "
		       "height=%u field=%u bytesperline=%u sizeimage=%u\n", device,
		       fourcc_text(format.fmt.pix.pixelformat, fourcc),
		       format.fmt.pix.width, format.fmt.pix.height,
		       format.fmt.pix.field, format.fmt.pix.bytesperline,
		       format.fmt.pix.sizeimage);
	}
	memset(&parameters, 0, sizeof(parameters));
	parameters.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
	if (xioctl(fd, VIDIOC_G_PARM, &parameters) == 0) {
		printf("CURRENT_INTERVAL device=%s numerator=%u denominator=%u "
		       "capability=0x%08x readbuffers=%u\n", device,
		       parameters.parm.capture.timeperframe.numerator,
		       parameters.parm.capture.timeperframe.denominator,
		       parameters.parm.capture.capability,
		       parameters.parm.capture.readbuffers);
	}
}

static int enumerate_node(const char *device, unsigned int *capture_nodes,
			  unsigned int *metadata_nodes, unsigned int *format_count,
			  unsigned int *size_count, unsigned int *interval_count,
			  unsigned int *input_count, unsigned int *standard_count)
{
	struct v4l2_capability capability;
	uint32_t caps;
	char driver[64], card[128], bus[128];
	int fd = open(device, O_RDWR | O_NONBLOCK | O_CLOEXEC);

	if (fd < 0) {
		fprintf(stderr, "OPEN_NODE_ERROR device=%s errno=%d\n", device, errno);
		return -1;
	}
	memset(&capability, 0, sizeof(capability));
	if (xioctl(fd, VIDIOC_QUERYCAP, &capability) < 0) {
		fprintf(stderr, "QUERYCAP_ERROR device=%s errno=%d\n", device, errno);
		close(fd);
		return -1;
	}
	caps = effective_capabilities(&capability);
	printf("NODE device=%s driver=%s card=%s bus_info=%s version=%u.%u.%u "
	       "capabilities=0x%08x device_caps=0x%08x capture=%u metadata=%u "
	       "streaming=%u\n", device,
	       safe_text(capability.driver, driver, sizeof(driver)),
	       safe_text(capability.card, card, sizeof(card)),
	       safe_text(capability.bus_info, bus, sizeof(bus)),
	       (capability.version >> 16) & 0xff,
	       (capability.version >> 8) & 0xff, capability.version & 0xff,
	       capability.capabilities, capability.device_caps,
	       !!(caps & V4L2_CAP_VIDEO_CAPTURE),
	       !!(caps & V4L2_CAP_META_CAPTURE), !!(caps & V4L2_CAP_STREAMING));

	if (caps & V4L2_CAP_VIDEO_CAPTURE) {
		++*capture_nodes;
		*format_count += enumerate_formats(fd, device,
						     V4L2_BUF_TYPE_VIDEO_CAPTURE,
						     size_count, interval_count);
		*input_count += enumerate_inputs(fd, device);
		*standard_count += enumerate_standards(fd, device);
		print_current_video_format(fd, device);
	}
	if (caps & V4L2_CAP_META_CAPTURE) {
		++*metadata_nodes;
		*format_count += enumerate_formats(fd, device,
						     V4L2_BUF_TYPE_META_CAPTURE,
						     size_count, interval_count);
	}
	close(fd);
	return 0;
}

static int enumerate_all(void)
{
	unsigned int nodes = 0, capture_nodes = 0, metadata_nodes = 0;
	unsigned int formats = 0, sizes = 0, intervals = 0, inputs = 0, standards = 0;
	unsigned int index;

	for (index = 0; index < MAX_VIDEO_NODES; ++index) {
		char device[32];

		snprintf(device, sizeof(device), "/dev/video%u", index);
		if (access(device, F_OK) != 0)
			continue;
		if (enumerate_node(device, &capture_nodes, &metadata_nodes, &formats,
				   &sizes, &intervals, &inputs, &standards) == 0)
			++nodes;
	}
	printf("ENUMERATION_SUMMARY result=%s nodes=%u capture_nodes=%u "
	       "metadata_nodes=%u formats=%u sizes=%u intervals=%u inputs=%u "
	       "standards=%u\n", nodes > 0 && capture_nodes > 0 ? "pass" : "fail",
	       nodes, capture_nodes, metadata_nodes, formats, sizes, intervals,
	       inputs, standards);
	return nodes > 0 && capture_nodes > 0 ? 0 : 1;
}

static int select_capture_device(char result[32])
{
	unsigned int index;

	for (index = 0; index < MAX_VIDEO_NODES; ++index) {
		struct v4l2_capability capability;
		uint32_t caps;
		char path[32];
		int fd;

		snprintf(path, sizeof(path), "/dev/video%u", index);
		fd = open(path, O_RDWR | O_NONBLOCK | O_CLOEXEC);
		if (fd < 0)
			continue;
		memset(&capability, 0, sizeof(capability));
		if (xioctl(fd, VIDIOC_QUERYCAP, &capability) == 0) {
			caps = effective_capabilities(&capability);
			if ((caps & V4L2_CAP_VIDEO_CAPTURE) &&
			    (caps & V4L2_CAP_STREAMING) &&
			    strcmp((const char *)capability.driver, "uvcvideo") == 0 &&
			    strncmp((const char *)capability.bus_info,
				    "usb-5200000.usb-1", 18) == 0) {
				close(fd);
				strcpy(result, path);
				return 0;
			}
		}
		close(fd);
	}
	return -1;
}

static uint64_t fnv1a64(const unsigned char *data, size_t size,
			unsigned long long *nonzero)
{
	uint64_t hash = UINT64_C(14695981039346656037);
	size_t index;

	*nonzero = 0;
	for (index = 0; index < size; ++index) {
		hash ^= data[index];
		hash *= UINT64_C(1099511628211);
		if (data[index] != 0)
			++*nonzero;
	}
	return hash;
}

static int capture_frames(const char *requested_device, uint32_t requested_fourcc,
			  unsigned int requested_width,
			  unsigned int requested_height, unsigned int requested_fps,
			  unsigned int frame_limit, unsigned int timeout_ms)
{
	struct v4l2_capability capability;
	struct v4l2_format format;
	struct v4l2_streamparm parameters;
	struct v4l2_requestbuffers request;
	struct mapped_buffer *buffers = NULL;
	uint64_t hashes[MAX_CAPTURE_FRAMES];
	unsigned int captured = 0, nonempty = 0, changed = 0, unique = 0;
	unsigned int startup_error_frames = 0, error_frames = 0, index, mapped = 0;
	unsigned long long total_bytes = 0, total_nonzero = 0;
	char automatic_device[32];
	const char *device = requested_device;
	char requested_text[5], negotiated_text[5];
	enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
	bool streaming = false;
	int fd = -1;
	int result = 1;

	if (device == NULL) {
		if (select_capture_device(automatic_device) < 0) {
			fprintf(stderr, "CAPTURE_ERROR stage=select reason=no_ms2131_capture_node\n");
			return 1;
		}
		device = automatic_device;
	}
	printf("CAPTURE_SELECTED device=%s selection=%s\n", device,
	       requested_device == NULL ? "automatic_ms2131_uvc" : "explicit");
	fd = open(device, O_RDWR | O_NONBLOCK | O_CLOEXEC);
	if (fd < 0) {
		fprintf(stderr, "CAPTURE_ERROR stage=open errno=%d\n", errno);
		goto cleanup;
	}
	memset(&capability, 0, sizeof(capability));
	if (xioctl(fd, VIDIOC_QUERYCAP, &capability) < 0 ||
	    !(effective_capabilities(&capability) & V4L2_CAP_VIDEO_CAPTURE) ||
	    !(effective_capabilities(&capability) & V4L2_CAP_STREAMING)) {
		fprintf(stderr, "CAPTURE_ERROR stage=querycap errno=%d\n", errno);
		goto cleanup;
	}

	{
		int input_index = -1;
		struct v4l2_input input;
		char input_name[128];

		if (xioctl(fd, VIDIOC_G_INPUT, &input_index) == 0) {
			memset(&input, 0, sizeof(input));
			input.index = (unsigned int)input_index;
			if (xioctl(fd, VIDIOC_ENUMINPUT, &input) == 0) {
				printf("CAPTURE_INPUT index=%u name=%s status=0x%08x "
				       "no_signal=%u\n", input.index,
				       safe_text(input.name, input_name, sizeof(input_name)),
				       input.status, !!(input.status & V4L2_IN_ST_NO_SIGNAL));
				if (input.status & V4L2_IN_ST_NO_SIGNAL) {
					fprintf(stderr, "CAPTURE_ERROR stage=input reason=no_signal\n");
					goto cleanup;
				}
			}
		}
	}

	memset(&format, 0, sizeof(format));
	format.type = type;
	format.fmt.pix.width = requested_width;
	format.fmt.pix.height = requested_height;
	format.fmt.pix.pixelformat = requested_fourcc;
	format.fmt.pix.field = V4L2_FIELD_ANY;
	if (xioctl(fd, VIDIOC_S_FMT, &format) < 0) {
		fprintf(stderr, "CAPTURE_ERROR stage=set_format errno=%d\n", errno);
		goto cleanup;
	}

	memset(&parameters, 0, sizeof(parameters));
	parameters.type = type;
	parameters.parm.capture.timeperframe.numerator = 1;
	parameters.parm.capture.timeperframe.denominator = requested_fps;
	if (xioctl(fd, VIDIOC_S_PARM, &parameters) < 0) {
		fprintf(stderr, "CAPTURE_ERROR stage=set_interval errno=%d\n", errno);
		goto cleanup;
	}
	printf("CAPTURE_CONFIG device=%s requested_fourcc=%s requested_width=%u "
	       "requested_height=%u requested_fps=%u negotiated_fourcc=%s "
	       "negotiated_width=%u negotiated_height=%u interval=%u/%u "
	       "bytesperline=%u sizeimage=%u field=%u\n", device,
	       fourcc_text(requested_fourcc, requested_text), requested_width,
	       requested_height, requested_fps,
	       fourcc_text(format.fmt.pix.pixelformat, negotiated_text),
	       format.fmt.pix.width, format.fmt.pix.height,
	       parameters.parm.capture.timeperframe.numerator,
	       parameters.parm.capture.timeperframe.denominator,
	       format.fmt.pix.bytesperline, format.fmt.pix.sizeimage,
	       format.fmt.pix.field);
	if (format.fmt.pix.pixelformat != requested_fourcc ||
	    format.fmt.pix.width != requested_width ||
	    format.fmt.pix.height != requested_height) {
		fprintf(stderr, "CAPTURE_ERROR stage=set_format reason=negotiated_mode_mismatch\n");
		goto cleanup;
	}

	memset(&request, 0, sizeof(request));
	request.count = 4;
	request.type = type;
	request.memory = V4L2_MEMORY_MMAP;
	if (xioctl(fd, VIDIOC_REQBUFS, &request) < 0 || request.count < 2) {
		fprintf(stderr, "CAPTURE_ERROR stage=request_buffers errno=%d count=%u\n",
			errno, request.count);
		goto cleanup;
	}
	buffers = calloc(request.count, sizeof(*buffers));
	if (buffers == NULL) {
		fprintf(stderr, "CAPTURE_ERROR stage=allocate errno=%d\n", errno);
		goto cleanup;
	}
	for (index = 0; index < request.count; ++index) {
		struct v4l2_buffer buffer;

		memset(&buffer, 0, sizeof(buffer));
		buffer.type = type;
		buffer.memory = V4L2_MEMORY_MMAP;
		buffer.index = index;
		if (xioctl(fd, VIDIOC_QUERYBUF, &buffer) < 0) {
			fprintf(stderr, "CAPTURE_ERROR stage=query_buffer errno=%d index=%u\n",
				errno, index);
			goto cleanup;
		}
		buffers[index].length = buffer.length;
		buffers[index].address = mmap(NULL, buffer.length, PROT_READ | PROT_WRITE,
					      MAP_SHARED, fd, buffer.m.offset);
		if (buffers[index].address == MAP_FAILED) {
			buffers[index].address = NULL;
			fprintf(stderr, "CAPTURE_ERROR stage=mmap errno=%d index=%u\n",
				errno, index);
			goto cleanup;
		}
		++mapped;
		if (xioctl(fd, VIDIOC_QBUF, &buffer) < 0) {
			fprintf(stderr, "CAPTURE_ERROR stage=queue_buffer errno=%d index=%u\n",
				errno, index);
			goto cleanup;
		}
	}
	if (xioctl(fd, VIDIOC_STREAMON, &type) < 0) {
		fprintf(stderr, "CAPTURE_ERROR stage=stream_on errno=%d\n", errno);
		goto cleanup;
	}
	streaming = true;

	while (captured < frame_limit) {
		struct pollfd descriptor = { .fd = fd, .events = POLLIN | POLLPRI };
		struct v4l2_buffer buffer;
		unsigned long long nonzero;
		uint64_t hash;
		int poll_result;

		do {
			poll_result = poll(&descriptor, 1, (int)timeout_ms);
		} while (poll_result < 0 && errno == EINTR);
		if (poll_result <= 0) {
			fprintf(stderr, "CAPTURE_ERROR stage=poll reason=%s errno=%d "
				"captured=%u\n", poll_result == 0 ? "timeout" : "failure",
				errno, captured);
			goto cleanup;
		}
		memset(&buffer, 0, sizeof(buffer));
		buffer.type = type;
		buffer.memory = V4L2_MEMORY_MMAP;
		if (xioctl(fd, VIDIOC_DQBUF, &buffer) < 0) {
			if (errno == EAGAIN)
				continue;
			fprintf(stderr, "CAPTURE_ERROR stage=dequeue errno=%d captured=%u\n",
				errno, captured);
			goto cleanup;
		}
		if (buffer.index >= request.count ||
		    buffer.bytesused > buffers[buffer.index].length) {
			fprintf(stderr, "CAPTURE_ERROR stage=validate_buffer index=%u bytes=%u\n",
				buffer.index, buffer.bytesused);
			goto cleanup;
		}
		/*
		 * A UVC isochronous stream can begin part-way through a frame.  The
		 * driver correctly marks that first short buffer ERROR; applications
		 * discard it as pre-roll.  Permit exactly one such buffer before the
		 * first valid frame, while keeping later or repeated errors fatal to
		 * the capture result.
		 */
		if ((buffer.flags & V4L2_BUF_FLAG_ERROR) && captured == 0 &&
		    startup_error_frames == 0) {
			++startup_error_frames;
			printf("FRAME_DISCARD phase=startup reason=error_flag sequence=%u "
			       "bytesused=%u timestamp=%ld.%06ld flags=0x%08x\n",
			       buffer.sequence, buffer.bytesused,
			       (long)buffer.timestamp.tv_sec,
			       (long)buffer.timestamp.tv_usec, buffer.flags);
			if (xioctl(fd, VIDIOC_QBUF, &buffer) < 0) {
				fprintf(stderr, "CAPTURE_ERROR stage=requeue_startup "
					"errno=%d\n", errno);
				goto cleanup;
			}
			continue;
		}
		hash = fnv1a64(buffers[buffer.index].address, buffer.bytesused, &nonzero);
		hashes[captured] = hash;
		if (buffer.bytesused > 0 && nonzero > 0)
			++nonempty;
		if (captured > 0 && hash != hashes[captured - 1])
			++changed;
		if (buffer.flags & V4L2_BUF_FLAG_ERROR)
			++error_frames;
		total_bytes += buffer.bytesused;
		total_nonzero += nonzero;
		printf("FRAME index=%u sequence=%u bytesused=%u nonzero_bytes=%llu "
		       "hash_fnv1a64=%016" PRIx64 " changed_from_previous=%u "
		       "timestamp=%ld.%06ld flags=0x%08x\n", captured,
		       buffer.sequence, buffer.bytesused, nonzero, hash,
		       captured > 0 && hash != hashes[captured - 1],
		       (long)buffer.timestamp.tv_sec, (long)buffer.timestamp.tv_usec,
		       buffer.flags);
		++captured;
		if (xioctl(fd, VIDIOC_QBUF, &buffer) < 0) {
			fprintf(stderr, "CAPTURE_ERROR stage=requeue errno=%d captured=%u\n",
				errno, captured);
			goto cleanup;
		}
	}
	for (index = 0; index < captured; ++index) {
		unsigned int previous;
		bool seen = false;

		for (previous = 0; previous < index; ++previous) {
			if (hashes[previous] == hashes[index]) {
				seen = true;
				break;
			}
		}
		if (!seen)
			++unique;
	}
	/* Reject a lone start-of-stream transition followed by a frozen picture. */
	result = captured == frame_limit && nonempty == frame_limit && unique >= 3 &&
		changed >= 2 && error_frames == 0 ? 0 : 1;
	printf("CAPTURE_SUMMARY result=%s device=%s frames=%u nonempty_frames=%u "
	       "changing_transitions=%u unique_hashes=%u total_bytes=%llu "
	       "total_nonzero_bytes=%llu startup_error_frames=%u error_frames=%u\n",
	       result == 0 ? "pass" : "fail", device, captured, nonempty, changed,
	       unique, total_bytes, total_nonzero, startup_error_frames, error_frames);

cleanup:
	if (streaming)
		(void)xioctl(fd, VIDIOC_STREAMOFF, &type);
	for (index = 0; index < mapped; ++index)
		(void)munmap(buffers[index].address, buffers[index].length);
	free(buffers);
	if (fd >= 0)
		close(fd);
	return result;
}

static void usage(const char *program)
{
	fprintf(stderr,
		"usage: %s --enumerate\n"
		"       %s --capture-auto [--fourcc YUYV] [--width 640] "
		"[--height 480] [--fps 30] [--frames 12] [--timeout-ms 3000]\n"
		"       %s --capture DEVICE [capture options]\n",
		program, program, program);
}

int main(int argc, char **argv)
{
	const char *device = NULL;
	uint32_t pixel_format = V4L2_PIX_FMT_YUYV;
	unsigned int width = 640, height = 480, fps = 30, frames = 12;
	unsigned int timeout_ms = 3000;
	bool enumerate = false, capture = false;
	int index;

	for (index = 1; index < argc; ++index) {
		if (strcmp(argv[index], "--enumerate") == 0) {
			enumerate = true;
		} else if (strcmp(argv[index], "--capture-auto") == 0) {
			capture = true;
			device = NULL;
		} else if (strcmp(argv[index], "--capture") == 0 && index + 1 < argc) {
			capture = true;
			device = argv[++index];
		} else if (strcmp(argv[index], "--fourcc") == 0 && index + 1 < argc) {
			pixel_format = parse_fourcc(argv[++index]);
		} else if (strcmp(argv[index], "--width") == 0 && index + 1 < argc) {
			width = parse_unsigned("width", argv[++index], 1, 16384);
		} else if (strcmp(argv[index], "--height") == 0 && index + 1 < argc) {
			height = parse_unsigned("height", argv[++index], 1, 16384);
		} else if (strcmp(argv[index], "--fps") == 0 && index + 1 < argc) {
			fps = parse_unsigned("fps", argv[++index], 1, 1000);
		} else if (strcmp(argv[index], "--frames") == 0 && index + 1 < argc) {
			frames = parse_unsigned("frames", argv[++index], 2,
						MAX_CAPTURE_FRAMES);
		} else if (strcmp(argv[index], "--timeout-ms") == 0 && index + 1 < argc) {
			timeout_ms = parse_unsigned("timeout-ms", argv[++index], 100, 60000);
		} else {
			usage(argv[0]);
			return 2;
		}
	}
	if (enumerate == capture) {
		usage(argv[0]);
		return 2;
	}
	if (enumerate)
		return enumerate_all();
	return capture_frames(device, pixel_format, width, height, fps, frames,
			      timeout_ms);
}
