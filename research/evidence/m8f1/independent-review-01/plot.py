#!/usr/bin/env python3
import csv,pathlib
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt']='m8f1-independent-review-01'
import matplotlib.pyplot as plt
p=pathlib.Path(__file__).parent
with (p/'series.csv').open() as f:rows=list(csv.DictReader(f))
x=[float(r['elapsed_h']) for r in rows]
fig,axs=plt.subplots(4,1,figsize=(11,12),sharex=True,layout='constrained')
for ax,keys in zip(axs,[['main_Pss_Anon_KiB','main_Private_Dirty_KiB','main_Anonymous_KiB'],['MemAvailable_KiB'],['AnonPages_KiB','Shmem_KiB'],['Slab_KiB']]):
 for k in keys:ax.plot(x,[float(r[k])/1024 if r[k] else float('nan') for r in rows],label=k.replace('_KiB',''),linewidth=1)
 ax.axvline(43226.807410373/3600,color='black',ls='--',lw=1,label='Scheduled restart');ax.set_ylabel('MiB');ax.grid(alpha=.25);ax.legend(loc='best',fontsize=8)
axs[-1].set_xlabel('Hours since observation start (bridge monotonic time)')
fig.suptitle('M8-F1 observation 01: raw archived samples\nDiagnostic evidence; zero qualification duration')
fig.savefig(p/'memory.png',dpi=150)
fig.savefig(p/'memory.svg',metadata={'Date':None})
v=p/'memory.svg';v.write_text('\n'.join(line.rstrip() for line in v.read_text().splitlines())+'\n')
