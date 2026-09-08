/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "libs/frame.h"
#include "ustreamer/encoders/hw/encoder.h"
#include <linux/videodev2.h>
int main(int argc,char **argv) {
    if(argc!=3) return 2;
    FILE *f=fopen(argv[1],"rb");if(!f) return 2;
    if(fseek(f,0,SEEK_END)) return 2;
    long length=ftell(f);if(length<125 || length>8*1024*1024) return 2;
    rewind(f);
    us_frame_s *src=us_frame_init(), *dest=us_frame_init();
    us_frame_realloc_data(src,length);
    if(fread(src->data,1,length,f)!=(size_t)length) return 2;
    fclose(f);src->used=length;src->format=V4L2_PIX_FMT_MJPEG;
    src->grab_begin_ts=123.456L;
    us_hw_encoder_compress(src,dest);
    f=fopen(argv[2],"wb");if(!f) return 2;
    if(fwrite(dest->data,1,dest->used,f)!=dest->used) return 2;
    if(fclose(f)) return 2;
    us_frame_destroy(src);us_frame_destroy(dest);return 0;
}
