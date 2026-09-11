# M8-F2 offline attribution

All 737 raw command samples independently matched to controller records; all 6,393 archive members rehashed. Original archive unchanged. Allocation bytes, not apparent file length. Shmem and MemAvailable are system counters; overlapping classes are not summed.

| Metric | Initial bytes | Final bytes | Delta bytes | Nondecreasing |
| --- | ---: | ---: | ---: | --- |
| /var/log | 11956224 | 47292416 | 35336192 | True |
| /var/log/journal | 11927552 | 37986304 | 26058752 | True |
| /run/log/journal | 0 | 0 | 0 | True |
| /var/log/nginx | 24576 | 9302016 | 9277440 | True |
| Shmem | 362143744 | 401231872 | 39088128 | False |
| MemAvailable | 488132608 | 453672960 | -34459648 | False |

## Hourly medians and growth

OLS growth within each hour is descriptive, not a pass threshold. Hour 12 is partial and includes the scheduled restart.

| Hour | Metric | Median bytes | OLS bytes/hour | Endpoint delta bytes |
| --- | --- | ---: | ---: | ---: |
| 0 | /var/log | 12331008.0 | 754255.021 | 749568 |
| 0 | /var/log/journal | 11927552.0 | 0.000 | 0 |
| 0 | /run/log/journal | 0.0 | 0.000 | 0 |
| 0 | /var/log/nginx | 399360.0 | 754255.021 | 749568 |
| 0 | Shmem | 362520576.0 | 753517.717 | 749568 |
| 0 | MemAvailable | 490373120.0 | -597017.453 | 3866624 |
| 1 | /var/log | 13084672.0 | 754505.849 | 741376 |
| 1 | /var/log/journal | 11927552.0 | 0.000 | 0 |
| 1 | /run/log/journal | 0.0 | 0.000 | 0 |
| 1 | /var/log/nginx | 1153024.0 | 754505.849 | 741376 |
| 1 | Shmem | 363272192.0 | 754396.589 | 741376 |
| 1 | MemAvailable | 488976384.0 | 1646016.760 | 4288512 |
| 2 | /var/log | 16820224.0 | 9702789.435 | 6705152 |
| 2 | /var/log/journal | 14909440.0 | 8948088.344 | 5963776 |
| 2 | /run/log/journal | 0.0 | 0.000 | 0 |
| 2 | /var/log/nginx | 1906688.0 | 754701.091 | 741376 |
| 2 | Shmem | 367007744.0 | 9702530.160 | 6705152 |
| 2 | MemAvailable | 483885056.0 | -16239568.319 | -19058688 |
| 3 | /var/log | 20559872.0 | 754400.417 | 741376 |
| 3 | /var/log/journal | 17891328.0 | 0.000 | 0 |
| 3 | /run/log/journal | 0.0 | 0.000 | 0 |
| 3 | /var/log/nginx | 2664448.0 | 754400.417 | 741376 |
| 3 | Shmem | 371009536.0 | 1005457.605 | 1003520 |
| 3 | MemAvailable | 468228096.0 | -4210909.783 | -5681152 |
| 4 | /var/log | 21311488.0 | 753300.963 | 737280 |
| 4 | /var/log/journal | 17891328.0 | 0.000 | 0 |
| 4 | /run/log/journal | 0.0 | 0.000 | 0 |
| 4 | /var/log/nginx | 3416064.0 | 753300.963 | 737280 |
| 4 | Shmem | 371761152.0 | 753725.348 | 741376 |
| 4 | MemAvailable | 464807936.0 | -2960928.295 | 6500352 |
| 5 | /var/log | 28026880.0 | 8708860.175 | 6705152 |
| 5 | /var/log/journal | 23855104.0 | 7954486.089 | 5963776 |
| 5 | /run/log/journal | 0.0 | 0.000 | 0 |
| 5 | /var/log/nginx | 4167680.0 | 754374.085 | 741376 |
| 5 | Shmem | 378476544.0 | 8708265.948 | 6705152 |
| 5 | MemAvailable | 454643712.0 | -13075381.537 | -10711040 |
| 6 | /var/log | 28786688.0 | 2735600.313 | 2945024 |
| 6 | /var/log/journal | 23855104.0 | 1980658.055 | 2203648 |
| 6 | /run/log/journal | 0.0 | 0.000 | 0 |
| 6 | /var/log/nginx | 4927488.0 | 754942.258 | 741376 |
| 6 | Shmem | 379236352.0 | 2736644.351 | 2945024 |
| 6 | MemAvailable | 449542144.0 | -8074592.073 | -1097728 |
| 7 | /var/log | 31741952.0 | 753067.088 | 741376 |
| 7 | /var/log/journal | 26058752.0 | 0.000 | 0 |
| 7 | /run/log/journal | 0.0 | 0.000 | 0 |
| 7 | /var/log/nginx | 5679104.0 | 753067.088 | 741376 |
| 7 | Shmem | 382191616.0 | 752759.660 | 741376 |
| 7 | MemAvailable | 443064320.0 | -7253726.554 | -4280320 |
| 8 | /var/log | 38459392.0 | 6111617.660 | 6705152 |
| 8 | /var/log/journal | 32022528.0 | 5357591.860 | 5963776 |
| 8 | /run/log/journal | 0.0 | 0.000 | 0 |
| 8 | /var/log/nginx | 6432768.0 | 754025.801 | 741376 |
| 8 | Shmem | 388909056.0 | 6111692.695 | 6705152 |
| 8 | MemAvailable | 433246208.0 | -9409649.287 | -8413184 |
| 9 | /var/log | 39213056.0 | 754960.201 | 741376 |
| 9 | /var/log/journal | 32022528.0 | 0.000 | 0 |
| 9 | /run/log/journal | 0.0 | 0.000 | 0 |
| 9 | /var/log/nginx | 7186432.0 | 754960.201 | 741376 |
| 9 | Shmem | 393152512.0 | 5843380.551 | 4231168 |
| 9 | MemAvailable | 426645504.0 | -8637463.966 | -9289728 |
| 10 | /var/log | 39970816.0 | 754157.605 | 741376 |
| 10 | /var/log/journal | 32022528.0 | 0.000 | 0 |
| 10 | /run/log/journal | 0.0 | 0.000 | 0 |
| 10 | /var/log/nginx | 7944192.0 | 754396.416 | 741376 |
| 10 | Shmem | 393910272.0 | 754034.649 | 741376 |
| 10 | MemAvailable | 420104192.0 | -4003620.839 | -2605056 |
| 11 | /var/log | 46686208.0 | 1908277.889 | 6717440 |
| 11 | /var/log/journal | 37986304.0 | 1153683.095 | 5963776 |
| 11 | /run/log/journal | 0.0 | 0.000 | 0 |
| 11 | /var/log/nginx | 8695808.0 | 754594.793 | 753664 |
| 11 | Shmem | 400625664.0 | 1908339.720 | 6717440 |
| 11 | MemAvailable | 413855744.0 | -1294621.401 | -4313088 |
| 12 | /var/log | 47185920 | 810680.088 | 221184 |
| 12 | /var/log/journal | 37986304 | 0.000 | 0 |
| 12 | /run/log/journal | 0 | 0.000 | 0 |
| 12 | /var/log/nginx | 9195520 | 810680.088 | 221184 |
| 12 | Shmem | 401125376 | 940758.701 | 221184 |
| 12 | MemAvailable | 452415488 | -18899820.475 | 40534016 |

## Terminal attribution

The original 6.414 MiB is exactly 6725632 bytes between first/last 15-minute medians of the independently identified terminal 76-sample plateau. `/var/log/journal` contributes 5963776 bytes; `/var/log/nginx` contributes 761856 bytes. Both contribute; neither alone accounts for the total. `/run/log/journal` contributes zero. Directory scans are sequential, not atomic; residual histogram is retained in measurements.json.

## Journal generators

Rendered text bytes approximate serialization cost, not compressed journal disk allocation. Structured systemd unit fields were not archived.

| Identifier | Count | Rendered bytes |
| --- | ---: | ---: |
| kvmd | 53307 | 14447110 |
| runuser | 5890 | 628942 |
| sshd-session | 5775 | 706682 |
| sudo | 3465 | 357264 |
| unix_chkpwd | 2310 | 209678 |
| systemd | 19 | 1858 |

No aggregate decrease or rotation/drop message observed. No per-file journal identities archived: rotation without net decrease cannot be excluded; bound not demonstrated.

Full numeric outputs and request categories: [measurements.json](measurements.json). Raw sample series: [series.csv](series.csv). M8-F remains OPEN; P1 GATED; no qualification credit.
