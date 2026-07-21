# ARE Truth Spine Sustained Load Benchmark

Date: 2026-07-13 UTC

Purpose: measure ARE Truth Spine write, recall, and verify latency under sustained continuous write load while concurrent semantic extraction and real evidence admission run beside it. This is technical uncertainty evidence, not a marketing benchmark.

## Workload

Command:

```bash
./venv/bin/python benchmarks/are_truth_spine_sustained_load.py \
  --duration-s 120 \
  --bucket-s 10 \
  --write-threads 2 \
  --admission-threads 1 \
  --recall-interval-s 2 \
  --verify-interval-s 10 \
  --results-dir benchmark_results \
  --live-federal-register \
  --live-pages 15 \
  --live-per-page 100 \
  --live-delay-s 0.2
```

Corpus:
- Type: live Federal Register official API fetch
- Query: `artificial intelligence`
- Endpoint: `https://www.federalregister.gov/api/v1/documents.json`
- Records loaded: `657`
- Evidence content: official Federal Register records; no fabricated evidence text

Runtime roles:
- `2` continuous ARE write workers
- `1` evidence admission worker using `AdmissionGate.admit()`
- semantic extraction after each admission attempt, writing extraction events to ARE
- recall probe every `2s`
- verify probe every `10s`
- isolated ARE root under `benchmark_results`, not production memory

Raw artifacts:
- `benchmark_results/are_sustained_20260713T165445Z/raw_samples.csv`
- `benchmark_results/are_sustained_20260713T165445Z/latency_buckets.csv`
- `benchmark_results/are_sustained_20260713T165445Z/summary.json`
- `benchmark_results/are_sustained_20260713T165445Z/run_config.json`

## Aggregate Result

Final Truth Spine verification:

```json
{
  "valid": true,
  "records": 5120,
  "previous_hash": "e93fa1db8c63565cd9aa08e22ed3e22e7821c9285c52da4569ffd14636fe2b5e"
}
```

Aggregate latency:

| Operation | Count | Errors | p50 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|
| write | 3466 | 0 | 55.705731734633446 | 182.6601637993007 | 351.5860056504607 |
| admit | 941 | 0 | 82.2580885142088 | 178.0663652345538 | 274.58053920418024 |
| semantic_extract | 941 | 0 | 46.35549057275057 | 120.80125939100982 | 269.180104136467 |
| recall | 56 | 0 | 160.78240610659122 | 371.7069452162834 | 404.64366134256124 |
| verify | 12 | 0 | 149.26315285265446 | 229.18065596371892 | 232.53906518220901 |

## Latency Curve

10-second bucket p50/p99 latency in milliseconds:

| Window s | write p50 | write p99 | admit p50 | admit p99 | recall p50 | recall p99 | verify p50 | verify p99 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0-10 | 29.75783310830593 | 47.15442527085542 | 34.48640555143356 | 47.92866261675954 | 46.191112138330936 | 64.12831898778677 | 0.0035353004932403564 | 0.0035353004932403564 |
| 10-20 | 42.87420120090246 | 70.42020301334546 | 51.97061225771904 | 76.42350074835123 | 74.14090540260077 | 96.99160795658827 | 37.459963001310825 | 37.459963001310825 |
| 20-30 | 58.905407786369324 | 99.49047643691317 | 68.96236352622509 | 118.38081928901373 | 111.3060675561428 | 117.8969507664442 | 66.40204787254333 | 66.40204787254333 |
| 30-40 | 67.911590449512 | 109.8150490969418 | 78.86522961780429 | 135.07659232243904 | 127.91161239147186 | 154.75428998470306 | 114.26946986466646 | 114.26946986466646 |
| 40-50 | 78.61917233094573 | 133.71613087132567 | 90.58227436617017 | 139.46520427241921 | 114.59595523774624 | 164.89814035594463 | 123.19419346749783 | 123.19419346749783 |
| 50-60 | 76.08865387737751 | 153.35324712097645 | 101.99587885290384 | 207.73692447692142 | 132.23047275096178 | 269.30834006518126 | 135.38648281246424 | 135.38648281246424 |
| 60-70 | 74.69218410551548 | 175.17600467428565 | 119.56023890525103 | 209.7424302250146 | 192.62665649875998 | 228.9378130529076 | 183.751511387527 | 183.751511387527 |
| 70-80 | 100.75473506003618 | 184.5629697665573 | 116.6933560743928 | 240.64297381788478 | 203.46361864358187 | 230.73827631771564 | 163.13982289284468 | 163.13982289284468 |
| 80-90 | 117.5639284774661 | 223.52500345557763 | 82.34753459692001 | 180.65299384295852 | 255.40398247539997 | 400.18856156617403 | 202.00807228684425 | 202.00807228684425 |
| 90-100 | 124.8878394253552 | 213.09835026040682 | 89.02632724493742 | 137.93269953690466 | 286.17886546999216 | 312.3656813427806 | 186.1899346113205 | 186.1899346113205 |
| 100-110 | 129.49983216822147 | 224.41142005845916 | 88.56339426711202 | 126.33557823486623 | 280.37675144150853 | 343.66335864178836 | 232.53906518220901 | 232.53906518220901 |
| 110-120 | 131.24664220958948 | 225.52591742947703 | 94.42971926182508 | 136.14057600498197 | 243.46298817545176 | 334.2075565829873 | 182.62236658483744 | 182.62236658483744 |

## Observed Degradation

Latency did degrade during the sustained run.

- Write p50 rose from `29.75783310830593 ms` in the first bucket to `131.24664220958948 ms` in the final full bucket.
- Write p99 rose from `47.15442527085542 ms` to `225.52591742947703 ms`.
- Recall p50 rose from `46.191112138330936 ms` to `243.46298817545176 ms`.
- Recall p99 rose from `64.12831898778677 ms` to `334.2075565829873 ms`, with a maximum observed recall latency of `404.64366134256124 ms`.
- Verify latency rose from a near-empty-chain `0.0035353004932403564 ms` first probe to `182.62236658483744 ms` in the final full bucket, with max observed verify latency `232.53906518220901 ms`.

The degradation is expected from current implementation details:
- `TruthSpine._sequence_number()` recounts segment lines during each append.
- `TruthSpine.envelopes()` rereads segment JSONL files for recall and verify.
- `AREStore._search_memories()` scans envelopes in process for recall.
- `TruthSpine.verify()` walks the full persistent chain.

No operation errors were recorded, and final chain verification remained valid. The technical uncertainty is not correctness under this load; it is latency growth under larger sustained chains and concurrent recall/verify.

## Limitations

- This was a 120-second single-host run, not an overnight or multi-day soak.
- The live corpus contained `657` official Federal Register records. Admission attempts exceeded that count, so later admission attempts encountered canonical duplicate reuse.
- The benchmark used local disk and Python threads. It does not characterize distributed writers, networked volumes, Postgres projection latency, GPU extraction, or a production service mesh.
- Verify samples are sparse by design: one probe every 10 seconds.
- Recall probes used business-lane text search through the current in-process scan implementation, not a vector index.

## Reproducibility

The benchmark runner is:

`benchmarks/are_truth_spine_sustained_load.py`

Short shakedown command:

```bash
./venv/bin/python benchmarks/are_truth_spine_sustained_load.py \
  --duration-s 5 \
  --bucket-s 1 \
  --write-threads 1 \
  --admission-threads 1 \
  --recall-interval-s 1 \
  --verify-interval-s 2 \
  --results-dir /tmp/are_bench_live_shakedown \
  --live-federal-register \
  --live-pages 1 \
  --live-per-page 10 \
  --live-delay-s 0
```
