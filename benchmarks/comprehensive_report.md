# Comprehensive Benchmark Report

Auto-generato da `benchmarks/bench_comprehensive.py`. Tokenizer `cl100k_base`.

## Token totali

### @ 10 msg

| Workload | json_min | toon | adp_base | adp_static | adp_dyn_cold | adp_full_stack |
|---|---:|---:|---:|---:|---:|---:|
| status_polling | 751 | 849 | 693 | 693 | 693 | 397 |
| tool_use | 367 | 381 | 347 | 342 | 347 | 333 |
| long_narrative | 788 | 758 | 748 | 748 | 748 | 748 |
| etl_pipeline | 11,499 | 14,299 | 8,581 | 8,581 | 5,990 | 5,625 |
| multi_agent_broadcast | 460 | 452 | 432 | 422 | 432 | 404 |
| db_query_response | 2,952 | 2,017 | 1,747 | 1,752 | 1,822 | 1,658 |
| mixed | 1,662 | 1,969 | 1,317 | 1,315 | 1,141 | 1,023 |

### @ 50 msg

| Workload | json_min | toon | adp_base | adp_static | adp_dyn_cold | adp_full_stack |
|---|---:|---:|---:|---:|---:|---:|
| status_polling | 3,762 | 4,252 | 3,472 | 3,472 | 3,472 | 1,692 |
| tool_use | 2,127 | 2,086 | 1,859 | 1,834 | 1,875 | 1,755 |
| long_narrative | 3,823 | 3,673 | 3,623 | 3,623 | 3,623 | 3,623 |
| etl_pipeline | 58,220 | 72,220 | 43,622 | 43,622 | 30,390 | 28,706 |
| multi_agent_broadcast | 2,300 | 2,260 | 2,160 | 2,110 | 2,160 | 2,018 |
| db_query_response | 14,784 | 10,109 | 8,759 | 8,784 | 8,884 | 8,221 |
| mixed | 12,128 | 14,255 | 9,361 | 9,350 | 7,386 | 6,930 |

### @ 100 msg

| Workload | json_min | toon | adp_base | adp_static | adp_dyn_cold | adp_full_stack |
|---|---:|---:|---:|---:|---:|---:|
| status_polling | 7,523 | 8,503 | 6,943 | 6,943 | 6,943 | 3,308 |
| tool_use | 4,246 | 4,154 | 3,710 | 3,660 | 3,734 | 3,519 |
| long_narrative | 7,748 | 7,448 | 7,348 | 7,348 | 7,348 | 7,348 |
| etl_pipeline | 116,647 | 144,647 | 87,449 | 87,449 | 60,890 | 57,583 |
| multi_agent_broadcast | 4,600 | 4,520 | 4,320 | 4,220 | 4,320 | 4,009 |
| db_query_response | 29,565 | 20,215 | 17,515 | 17,565 | 17,710 | 16,420 |
| mixed | 24,519 | 27,939 | 18,627 | 18,602 | 14,804 | 14,012 |

### @ 500 msg

| Workload | json_min | toon | adp_base | adp_static | adp_dyn_cold | adp_full_stack |
|---|---:|---:|---:|---:|---:|---:|
| status_polling | 37,642 | 42,542 | 34,742 | 34,742 | 34,742 | 16,282 |
| tool_use | 21,564 | 21,141 | 18,812 | 18,562 | 18,903 | 17,633 |
| long_narrative | 38,950 | 37,450 | 36,950 | 36,950 | 36,950 | 36,950 |
| etl_pipeline | 584,066 | 724,066 | 438,068 | 438,068 | 304,890 | 288,602 |
| multi_agent_broadcast | 23,000 | 22,600 | 21,609 | 21,109 | 21,609 | 19,932 |
| db_query_response | 147,772 | 101,022 | 87,523 | 87,773 | 88,126 | 81,940 |
| mixed | 135,825 | 151,957 | 101,551 | 101,459 | 80,282 | 76,735 |

## ADP full_stack vs TOON e JSON @ 100 msg

| Workload | JSON | TOON | ADP full | Δ vs JSON | Δ vs TOON |
|---|---:|---:|---:|---:|---:|
| status_polling | 7,523 | 8,503 | 3,308 | +56.0% | +61.1% |
| tool_use | 4,246 | 4,154 | 3,519 | +17.1% | +15.3% |
| long_narrative | 7,748 | 7,448 | 7,348 | +5.2% | +1.3% |
| etl_pipeline | 116,647 | 144,647 | 57,583 | +50.6% | +60.2% |
| multi_agent_broadcast | 4,600 | 4,520 | 4,009 | +12.8% | +11.3% |
| db_query_response | 29,565 | 20,215 | 16,420 | +44.5% | +18.8% |
| mixed | 24,519 | 27,939 | 14,012 | +42.9% | +49.8% |

## Costo $ stima per 1 conversazione di 1000 msg

Estrapolato linearmente dal run @ 100 msg, Claude Sonnet 4.6 ($3/Mtok).

| Workload | JSON 1k | TOON 1k | ADP full 1k | Risparmio vs TOON |
|---|---:|---:|---:|---:|
| status_polling | $0.2257 | $0.2551 | $0.0992 | $0.1558 |
| tool_use | $0.1274 | $0.1246 | $0.1056 | $0.0190 |
| long_narrative | $0.2324 | $0.2234 | $0.2204 | $0.0030 |
| etl_pipeline | $3.50 | $4.34 | $1.73 | $2.61 |
| multi_agent_broadcast | $0.1380 | $0.1356 | $0.1203 | $0.0153 |
| db_query_response | $0.8870 | $0.6065 | $0.4926 | $0.1139 |
| mixed | $0.7356 | $0.8382 | $0.4204 | $0.4178 |

## Latency encode median @ 100 msg (ms)

| Workload | json | toon | adp_full | decode adp_full median |
|---|---:|---:|---:|---:|
| status_polling | 0.003 | 0.025 | 0.031 | 0.036 |
| tool_use | 0.003 | 0.023 | 0.029 | 0.023 |
| long_narrative | 0.003 | 0.028 | 0.022 | 0.036 |
| etl_pipeline | 0.030 | 0.471 | 0.438 | 0.367 |
| multi_agent_broadcast | 0.003 | 0.021 | 0.023 | 0.025 |
| db_query_response | 0.016 | 0.168 | 0.145 | 0.141 |
| mixed | 0.004 | 0.026 | 0.035 | 0.034 |
