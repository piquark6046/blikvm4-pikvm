/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "taildiag.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <openssl/sha.h>
int main(int argc,char **argv) {
    if(argc<2) return 2;
    FILE *f=fopen(argv[1],"rb");if(!f) return 2;
    if(fseek(f,0,SEEK_END)) return 2;
    long length=ftell(f);if(length<0 || length>8*1024*1024) return 2;
    rewind(f);
    unsigned char *p=malloc((size_t)length+1);if(!p) return 2;
    if(fread(p,1,length,f)!=(size_t)length) return 2;
    fclose(f);
    unsigned char before[32],after[32];SHA256(p,length,before);
    if(argc==2) {us_taildiag_describe(stdout,p,length);puts("");}
    else {
        struct v4l2_buffer v={.index=7,.sequence=12345,.flags=8192,.bytesused=length,
            .timestamp={.tv_sec=123,.tv_usec=456789}};
        unsigned repeats=strcmp(argv[2],"burst")==0?100:1;
        for(unsigned i=0;i<repeats;++i) {
            errno=EDOM;
            size_t used=(size_t)length;
            if(strcmp(argv[2],"copy-origin")==0 || strcmp(argv[2],"ambiguous")==0) used-=12;
            v.bytesused=used;
            if(strcmp(argv[2],"ambiguous")==0) us_taildiag(0,p,used,length,&v,123.456L,0);
            us_taildiag(0,p,used,length,&v,123.456L,0);
            us_taildiag(1,p,length,length,NULL,123.456L,123.478901L);
            us_taildiag(2,p,length,length,NULL,123.456L,123.478901L);
            if(errno!=EDOM) return 3;
        }
        if(strcmp(argv[2],"bounds")==0) {
            us_taildiag(0,p,length+1,length,&v,123.456L,0);
            us_taildiag(0,p,8*1024*1024+1,8*1024*1024+1,&v,123.456L,0);
        }
        if(strcmp(argv[2],"flush")==0) {
            struct timespec delay={.tv_sec=2,.tv_nsec=100000000};nanosleep(&delay,NULL);
        }
    }
    SHA256(p,length,after);free(p);
    return memcmp(before,after,32)?4:0;
}
