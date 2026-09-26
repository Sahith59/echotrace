# ASVspoof 5 protocol preparation

Source: https://zenodo.org/records/14498691

Official 20,669,392-byte protocol archive downloaded and verified against published MD5 `865d0e894ea9f686f0f37e5ae3ae3616`. Relevant regular files were read from the tar archive explicitly, without bulk filesystem extraction. README and license saved with ignored local artifacts. The new importer then validated all records and wrote separate manifests without repartitioning.

| Partition | Rows | Genuine | Spoof | Speaker IDs |
|---|---:|---:|---:|---:|
| Train | 182,357 | 18,797 | 163,560 | 400 |
| Development Track1 | 140,950 | 31,334 | 109,616 | 785 |
| Evaluation Track1 | 680,774 | 138,688 | 542,086 | 737 |

Hashes and exact metadata summaries are retained beside this report. These are metadata statistics, not model performance. The large audio archives have NOT been downloaded, decoded, or scored. Local manifests are under backend/artifacts/asvspoof5. Audio installation destination is pending user input; the train+dev archive plan is configs/asvspoof5-downloads.json. Do not train or tune on the official evaluation partition. Audio sample limits remain the current120seconds/50MiB until corpus durations are audited.
