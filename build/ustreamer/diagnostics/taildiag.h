/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include <stddef.h>
#include <stdio.h>
#include <time.h>
#include <linux/videodev2.h>
/* No return value may influence capture, encoding or HTTP decisions. */
void us_taildiag(unsigned stage, const unsigned char *data, size_t used,
                 size_t allocated, const struct v4l2_buffer *v4l2,
                 long double grab, long double encode);
/* Shared by the runtime writer and the offline fixture harness. */
void us_taildiag_describe(FILE *out, const unsigned char *data, size_t used);
