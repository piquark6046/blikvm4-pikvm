/* SPDX-License-Identifier: GPL-3.0-or-later
 * M8-F0 diagnostic only. No frame mutation, policy or recovery decisions.
 */
#include "taildiag.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <openssl/sha.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define MAX_BYTES (8U * 1024U * 1024U)
#define SLOTS 4
#define RECENT 2048
#define LIMIT 64
#define DISK_BUDGET (128U * 1024U * 1024U)
static const char *stages[] = {"dqbuf", "hw_jpeg", "http_exposed"};
static void hex(FILE *f, const unsigned char *p, size_t n) {
    fputc('"', f);
    for (size_t i = 0; i < n; ++i) fprintf(f, "%02x", p[i]);
    fputc('"', f);
}
static void sha(const unsigned char *p, size_t n, unsigned char hash[32]) {
    SHA256(p, n, hash);
}
static uint32_t le32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static size_t final_eoi(const unsigned char *p, size_t n) {
    for (size_t i = n; i > 1; --i)
        if (p[i-2] == 255 && p[i-1] == 217) return i-2;
    return SIZE_MAX;
}
/* Structural walk skips APP/COM/table data and stuffed entropy bytes. This is
 * diagnostic marker evidence, not a replacement JPEG decoder/validator. */
static bool structural_eoi(const unsigned char *p, size_t n) {
    if (n < 4 || p[0] != 255 || p[1] != 216) return false;
    size_t i = 2;
    bool entropy = false;
    while (i < n) {
        if (entropy && p[i] != 255) { ++i; continue; }
        if (p[i++] != 255) return false;
        while (i < n && p[i] == 255) ++i;
        if (i >= n) return false;
        unsigned m = p[i++];
        if (entropy && (m == 0 || (m >= 208 && m <= 215))) continue;
        if (m == 217) return true;
        if (m == 0 || m == 216 || (m >= 208 && m <= 215)) return false;
        if (m == 1) continue;
        if (n-i < 2) return false;
        size_t length = (size_t)p[i]*256 + p[i+1];
        if (length < 2 || length > n-i) return false;
        i += length;
        entropy = (m == 218);
    }
    return false;
}
static void uvc(FILE *f, const unsigned char *p, size_t n) {
    if (n < 2) { fputs("null", f); return; }
    unsigned flags = p[1], need = 2 + ((flags & 4) ? 4 : 0) + ((flags & 8) ? 6 : 0);
    bool fields = n >= need && p[0] >= need;
    fprintf(f, "{\"bHeaderLength\":%u,\"bmHeaderInfo\":%u,\"FID\":%u,\"EOF\":%u,"
        "\"PTS_present\":%s,\"SCR_present\":%s,\"ERR\":%u,\"STI\":%u,\"reserved\":%u,\"EOH\":%u,"
        "\"required_length\":%u,\"length_matches_tail\":%s,\"fields_complete\":%s,"
        "\"header_shaped_only\":%s,\"PTS\":", p[0],flags,flags&1,(flags>>1)&1,
        flags&4?"true":"false",flags&8?"true":"false",(flags>>6)&1,(flags>>5)&1,
        (flags>>4)&1,(flags>>7)&1,need,p[0]==n?"true":"false",fields?"true":"false",
        fields && p[0]==n && !(flags&16) && (flags&128)?"true":"false");
    if ((flags&4) && n>=6 && p[0]>=6) fprintf(f,"%"PRIu32,le32(p+2)); else fputs("null",f);
    fputs(",\"SCR_clock\":",f);
    size_t offset = 2 + ((flags&4)?4:0);
    if ((flags&8) && fields) fprintf(f,"%"PRIu32,le32(p+offset)); else fputs("null",f);
    fputs(",\"SCR_SOF_raw\":",f);
    if ((flags&8) && fields) fprintf(f,"%u",p[offset+4]+256U*p[offset+5]); else fputs("null",f);
    fputs(",\"SCR_SOF\":",f);
    if ((flags&8) && fields) fprintf(f,"%u",(p[offset+4]+256U*p[offset+5])&2047); else fputs("null",f);
    fputs(",\"SCR_reserved\":",f);
    if ((flags&8) && fields) fprintf(f,"%u",(p[offset+4]+256U*p[offset+5])>>11); else fputs("null",f);
    fputc('}',f);
}
void us_taildiag_describe(FILE *f, const unsigned char *p, size_t n) {
    size_t end = final_eoi(p,n), soi = SIZE_MAX;
    for (size_t i=0;i+1<n;++i) if(p[i]==255 && p[i+1]==216) {soi=i;break;}
    fprintf(f,"{\"bytesused\":%zu,\"soi_offset\":",n);
    if(soi==SIZE_MAX) fputs("null",f); else fprintf(f,"%zu",soi);
    fputs(",\"eoi_offsets\":[",f);
    bool comma=false;
    for(size_t i=0;i+1<n;++i) if(p[i]==255 && p[i+1]==217) {
        fprintf(f,"%s%zu",comma?",":"",i);comma=true;
    }
    fprintf(f,"],\"structural_eoi_exists\":%s,\"suspicious\":%s,\"final_eoi_offset\":",
        structural_eoi(p,n)?"true":"false",
        end!=SIZE_MAX && end+2<n && structural_eoi(p,n)?"true":"false");
    if(end==SIZE_MAX) fputs("null,\"trailing_length\":null,\"trailing_hex\":null,\"uvc_candidate\":null",f);
    else {
        fprintf(f,"%zu,\"trailing_length\":%zu,\"trailing_hex\":",end,n-end-2);
        hex(f,p+end+2,n-end-2);fputs(",\"uvc_candidate\":",f);uvc(f,p+end+2,n-end-2);
    }
    fputs(",\"first64_hex\":",f);hex(f,p,n<64?n:64);
    fputs(",\"last64_hex\":",f);hex(f,p+(n<64?0:n-64),n<64?n:64);
    unsigned char hash[32];sha(p,n,hash);fputs(",\"sha256\":",f);hex(f,hash,32);
    fputs(",\"through_final_eoi_sha256\":",f);
    if(end==SIZE_MAX) fputs("null",f);else {sha(p,end+2,hash);hex(f,hash,32);}
    fputc('}',f);
}

typedef struct {
    unsigned stage;
    size_t used;
    long double grab, encode;
    struct timespec mono, real;
    struct v4l2_buffer v4l2;
    bool has_v4l2, suspicious, correlation_ambiguous;
    unsigned char hash[32];
} summary;
typedef struct {
    bool ready;
    summary row, prior[2];
    unsigned prior_count;
    unsigned ordinal;
    unsigned char *data;
} event;
static pthread_once_t once = PTHREAD_ONCE_INIT;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t wake = PTHREAD_COND_INITIALIZER;
static pthread_t thread;
static event queue[SLOTS];
static summary recent[RECENT];
static unsigned recent_pos, recent_count, accepted[3], written[3], full[3];
static unsigned snapshots, snapshots_written;
static uint64_t suppressed[3], oversized[3], inspected[3], suspicious_seen[3], metadata_misses[3], reserved_bytes;
static struct timespec last[3];
static int directory = -1;
static bool enabled, stopping;

static void metadata(FILE *f,const summary *s) {
    fprintf(f,"{\"stage\":\"%s\",\"pid\":%ld,\"monotonic\":%lld.%09ld,\"realtime\":%lld.%09ld,"
        "\"grab_begin_time\":\"%.6Lf\",\"encode_end_time\":\"%.6Lf\",\"bytesused\":%zu,"
        "\"suspicious\":%s,\"sha256\":",stages[s->stage],(long)getpid(),
        (long long)s->mono.tv_sec,s->mono.tv_nsec,(long long)s->real.tv_sec,s->real.tv_nsec,
        s->grab,s->encode,s->used,s->suspicious?"true":"false");
    hex(f,s->hash,32);
    fprintf(f,",\"correlation_ambiguous\":%s,\"v4l2\":",s->correlation_ambiguous?"true":"false");
    if(s->has_v4l2) fprintf(f,"{\"index\":%u,\"sequence\":%u,\"flags\":%u,\"bytesused\":%u,"
        "\"timestamp_sec\":%lld,\"timestamp_usec\":%lld}",s->v4l2.index,s->v4l2.sequence,
        s->v4l2.flags,s->v4l2.bytesused,(long long)s->v4l2.timestamp.tv_sec,(long long)s->v4l2.timestamp.tv_usec);
    else fputs("null",f);
    fputc('}',f);
}
static FILE *create(const char *name) {
    int fd=openat(directory,name,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    if(fd<0) return NULL;
    FILE *f=fdopen(fd,"wb");if(!f) close(fd);return f;
}
/* Observation 03 may create an empty flush.request when its multipart client
 * sees an anomaly. This preserves normal upstream hashes without HTTP changes.
 * Never called under the producer mutex; no regular frame payload is saved. */
static void flush_requested(void) {
    if(snapshots>=4) return;
    int fd=openat(directory,"flush.request",O_RDONLY|O_NONBLOCK|O_NOFOLLOW|O_CLOEXEC);
    if(fd<0) return;
    struct stat st;
    bool valid=fstat(fd,&st)==0 && S_ISREG(st.st_mode) && st.st_uid==geteuid() && st.st_size==0;
    close(fd);
    if(!valid) return;
    summary *copy=malloc(sizeof(recent));
    if(!copy) return;
    pthread_mutex_lock(&lock);
    uint64_t cost=RECENT*2048U+8192;
    if(cost>DISK_BUDGET-reserved_bytes) {pthread_mutex_unlock(&lock);free(copy);return;}
    reserved_bytes+=cost;
    unsigned count=recent_count;
    for(unsigned i=0;i<count;++i) copy[i]=recent[(recent_pos+RECENT-count+i)%RECENT];
    pthread_mutex_unlock(&lock);
    /* A new request created during this write remains for the next snapshot. */
    if(unlinkat(directory,"flush.request",0)) {free(copy);return;}
    char name[64];snprintf(name,sizeof(name),"recent-%03u.json",++snapshots);
    FILE *f=create(name);
    if(f) {
        fprintf(f,"{\"diagnostic_only\":true,\"request_realtime\":%lld.%09ld,\"boundaries\":[",
            (long long)st.st_mtim.tv_sec,st.st_mtim.tv_nsec);
        for(unsigned i=0;i<count;++i) {if(i) fputc(',',f);metadata(f,&copy[i]);}
        fputs("]}\n",f);
        bool ok=!ferror(f);if(fclose(f)) ok=false;
        if(ok) ++snapshots_written;
    }
    free(copy);
}
static void *writer(void *unused) {
    (void)unused;
    for(;;) {
        pthread_mutex_lock(&lock);
        unsigned slot;
        for(;;) {
            for(slot=0;slot<SLOTS;++slot) if(queue[slot].ready) break;
            if(slot<SLOTS || stopping) break;
            struct timespec deadline;
            clock_gettime(CLOCK_REALTIME,&deadline);++deadline.tv_sec;
            if(pthread_cond_timedwait(&wake,&lock,&deadline)==ETIMEDOUT) {
                pthread_mutex_unlock(&lock);flush_requested();pthread_mutex_lock(&lock);
            }
        }
        if(slot==SLOTS) {pthread_mutex_unlock(&lock);break;}
        event *e=&queue[slot]; /* ready stays set while writer owns payload */
        pthread_mutex_unlock(&lock);
        char name[96],payload[96];
        snprintf(name,sizeof(name),"%s-%03u.json",stages[e->row.stage],e->ordinal);
        snprintf(payload,sizeof(payload),"%s-%03u.bin",stages[e->row.stage],e->ordinal);
        bool saved=false;
        if(full[e->row.stage]<4) {
            FILE *f=create(payload);
            if(f) {
                bool ok=fwrite(e->data,1,e->row.used,f)==e->row.used;
                if(fclose(f)!=0) ok=false;
                saved=ok;
                if(ok) ++full[e->row.stage];
            }
        }
        FILE *f=create(name);
        if(f) {
            fputs("{\"qualification\":\"NOT_RUN\",\"boundary\":",f);metadata(f,&e->row);
            fputs(",\"prior_boundaries\":[",f);
            for(unsigned i=0;i<e->prior_count;++i) {if(i) fputc(',',f);metadata(f,&e->prior[i]);}
            fputs("],\"payload_file\":",f);
            if(saved) fprintf(f,"\"%s\"",payload);else fputs("null",f);
            fputs(",\"jpeg\":",f);us_taildiag_describe(f,e->data,e->row.used);fputs("}\n",f);
            bool ok=!ferror(f);if(fclose(f)!=0) ok=false;
            if(ok) ++written[e->row.stage];
        }
        pthread_mutex_lock(&lock);e->ready=false;pthread_mutex_unlock(&lock);
        flush_requested();
    }
    return NULL;
}
static void finish(void) {
    if(!enabled) return;
    pthread_mutex_lock(&lock);stopping=true;pthread_cond_signal(&wake);pthread_mutex_unlock(&lock);
    pthread_join(thread,NULL);
    FILE *f=create("summary.json");
    if(f) {
        fputs("{\"qualification\":\"NOT_RUN\",\"stages\":[",f);
        for(unsigned i=0;i<3;++i) fprintf(f,"%s{\"stage\":\"%s\",\"accepted\":%u,\"written\":%u,"
            "\"suppressed\":%"PRIu64",\"oversized_or_invalid_length\":%"PRIu64",\"inspected\":%"PRIu64","
            "\"suspicious_seen\":%"PRIu64",\"metadata_misses\":%"PRIu64"}",
            i?",":"",stages[i],accepted[i],written[i],suppressed[i],oversized[i],inspected[i],suspicious_seen[i],metadata_misses[i]);
        fprintf(f,"],\"snapshots\":%u,\"snapshots_written\":%u}\n",snapshots,snapshots_written);fclose(f);
    }
    close(directory);
    for(unsigned i=0;i<SLOTS;++i) free(queue[i].data);
}
static void initialize(void) {
    const char *path=getenv("USTREAMER_TAILDIAG_DIR");
    if(!path || !*path) return;
    directory=open(path,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    struct stat st;
    if(directory<0) return;
    if(fstat(directory,&st) || st.st_uid!=geteuid() || (st.st_mode&077)) goto fail;
    FILE *f=create("session.json");
    if(!f) goto fail;
    fprintf(f,"{\"diagnostic_only\":true,\"pid\":%ld,\"max_payload_bytes\":%u,"
        "\"queue_slots\":%u,\"per_stage_limit\":%u,\"min_interval_seconds\":1,"
        "\"full_payloads_per_stage\":4,\"recent_summaries\":%u,\"disk_budget_bytes\":%u}\n",(long)getpid(),MAX_BYTES,SLOTS,LIMIT,RECENT,DISK_BUDGET);
    if(fclose(f)) goto fail;
    for(unsigned i=0;i<SLOTS;++i) if(!(queue[i].data=malloc(MAX_BYTES))) goto fail;
    if(pthread_create(&thread,NULL,writer,NULL)) goto fail;
    enabled=true;atexit(finish);return;
fail:
    for(unsigned i=0;i<SLOTS;++i) {free(queue[i].data);queue[i].data=NULL;}
    close(directory);directory=-1;
}
void us_taildiag(unsigned stage,const unsigned char *p,size_t n,size_t allocated,
                 const struct v4l2_buffer *v,long double grab,long double encode) {
    int saved_errno=errno;
    pthread_once(&once,initialize);
    if(!enabled || stage>2) goto done;
    if(n>allocated || n>MAX_BYTES || (!p && n)) {
        pthread_mutex_lock(&lock);++oversized[stage];pthread_mutex_unlock(&lock);goto done;
    }
    summary s={.stage=stage,.used=n,.grab=grab,.encode=encode};
    clock_gettime(CLOCK_MONOTONIC,&s.mono);clock_gettime(CLOCK_REALTIME,&s.real);
    if(v) {s.v4l2=*v;s.has_v4l2=true;}
    size_t end=final_eoi(p,n);
    s.suspicious=end!=SIZE_MAX && end+2<n && structural_eoi(p,n);
    sha(p,n,s.hash); /* Bounded recent normal hashes allow proof of copy-origin anomalies. */
    pthread_mutex_lock(&lock);
    summary prior[2];unsigned count=0;
    ++inspected[stage];
    if(s.suspicious) ++suspicious_seen[stage];
    for(unsigned wanted=0;wanted<stage;++wanted) {
        summary *match=NULL;
        unsigned matches=0;
        for(unsigned j=0;j<recent_count;++j) {
            summary *r=&recent[(recent_pos+RECENT-1-j)%RECENT];
            if(r->stage==wanted && r->grab==grab && (wanted==0 || r->encode==encode)) {
                match=r;++matches;
            }
        }
        if(matches==1) {
            prior[count++]=*match;
            if(wanted==0 && match->has_v4l2) {s.v4l2=match->v4l2;s.has_v4l2=true;}
            if(match->correlation_ambiguous) s.correlation_ambiguous=true;
        } else if(matches>1) s.correlation_ambiguous=true;
    }
    if(stage && !s.has_v4l2) ++metadata_misses[stage];
    recent[recent_pos]=s;recent_pos=(recent_pos+1)%RECENT;
    if(recent_count<RECENT) ++recent_count;
    if(s.suspicious) {
        unsigned slot;
        for(slot=0;slot<SLOTS;++slot) if(!queue[slot].ready) break;
        double elapsed=(double)(s.mono.tv_sec-last[stage].tv_sec)+(s.mono.tv_nsec-last[stage].tv_nsec)/1e9;
        /* Conservative upper bound: all raw EOI offsets, full tail hex, raw payload, metadata. */
        uint64_t cost=12*(uint64_t)n+8192;
        if(accepted[stage]>=LIMIT || (accepted[stage] && elapsed<1) || slot==SLOTS || cost>DISK_BUDGET-reserved_bytes) ++suppressed[stage];
        else {
            reserved_bytes+=cost;
            event *e=&queue[slot];e->row=s;e->ordinal=++accepted[stage];
            e->prior_count=count;memcpy(e->prior,prior,count*sizeof(summary));
            memcpy(e->data,p,n);last[stage]=s.mono;e->ready=true;pthread_cond_signal(&wake);
        }
    }
    pthread_mutex_unlock(&lock);
done:
    errno=saved_errno;
}
