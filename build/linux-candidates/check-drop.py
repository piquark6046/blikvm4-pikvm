#!/usr/bin/env python3
from pathlib import Path
import subprocess,json
import argparse
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=a.output;r.mkdir(parents=True,exist_ok=True);s=(a.source/'drivers/media/usb/uvc/uvc_queue.c').read_text()
def function(name):
 start=s.index('static void '+name+'(');end=s.index('\n}',start)+2;return s[start:end]
c='''#include <stdbool.h>
#include <stddef.h>
#include <assert.h>
#define container_of(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))
enum { UVC_BUF_STATE_QUEUED, UVC_BUF_STATE_ERROR, UVC_BUF_STATE_DONE, VB2_BUF_STATE_ERROR, VB2_BUF_STATE_DONE };
struct kref {int unused;};struct uvc_video_queue {int unused;};
struct vb2_buffer {void *vb2_queue;unsigned int payload;};
struct vb2_v4l2_buffer {struct vb2_buffer vb2_buf;};
struct uvc_buffer {struct vb2_v4l2_buffer buf;unsigned int error;bool ms2131_bad_eof;unsigned int state,bytesused;struct kref ref;};
unsigned int uvc_no_drop_param;int requeued,done,last_state;
void *vb2_get_drv_priv(void *p){return p;}
void vb2_set_plane_payload(struct vb2_buffer *b,int plane,unsigned int n){(void)plane;b->payload=n;}
void uvc_buffer_queue(struct vb2_buffer *b){(void)b;requeued++;}
void vb2_buffer_done(struct vb2_buffer *b,int state){(void)b;done++;last_state=state;}
'''+function('uvc_queue_buffer_requeue')+'\n'+function('uvc_queue_buffer_complete')+'''
int main(void){
 struct uvc_video_queue q={0};
 for(unsigned int nodrop=0;nodrop<2;nodrop++)for(int bad=0;bad<2;bad++)for(int error=0;error<2;error++){
  struct uvc_buffer b={0};b.buf.vb2_buf.vb2_queue=&q;b.error=error;b.ms2131_bad_eof=bad;b.bytesused=1234;uvc_no_drop_param=nodrop;requeued=done=0;
  uvc_queue_buffer_complete(&b.ref);
  if(bad || (error&&!nodrop)){
   assert(requeued==1 && done==0 && !b.ms2131_bad_eof && !b.error && b.bytesused==0 && b.buf.vb2_buf.payload==0);
   b.bytesused=5678;uvc_queue_buffer_complete(&b.ref);assert(done==1 && b.buf.vb2_buf.payload==5678 && last_state==VB2_BUF_STATE_DONE);
  }else{assert(requeued==0 && done==1 && b.bytesused==1234 && b.buf.vb2_buf.payload==1234);assert(last_state==(error?VB2_BUF_STATE_ERROR:VB2_BUF_STATE_DONE));}
 }
 return 0;
}
'''
(r/'drop-test.c').write_text(c)
subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter','-Werror','-fsanitize=undefined','-o',str(r/'drop-test'),str(r/'drop-test.c')],check=True)
subprocess.run([str(r/'drop-test')],check=True)
result={'result':'passed','actual_functions':['uvc_queue_buffer_complete','uvc_queue_buffer_requeue'],'nodrop_values':[0,1],'error_and_quirk_combinations':8,'buffer_reuse_verified':True,'sanitizer':'undefined'}
(r/'drop-test.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
