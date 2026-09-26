"""Content-level independence audit for a locked acceptance manifest."""
from __future__ import annotations
import argparse, hashlib, json
from collections import Counter
from pathlib import Path
from .evaluation import load_manifest

def _prior_records(run):
    data=json.loads(Path(run).read_text())
    records=list(data.get("records") or [])
    provenance=data.get("training_provenance") or {}
    records += list(provenance.get("train") or []) + list(provenance.get("validation") or [])
    return records

def run(manifest,dataset_root,prior_runs,output):
    records=load_manifest(Path(manifest),Path(dataset_root))
    if len(records)!=2000 or Counter(r["label"] for r in records)!={0:1000,1:1000}:
        raise ValueError("Acceptance must be frozen at 1000 files per class")
    hashes=[r["sha256"] for r in records]
    if len(set(hashes))!=len(hashes):raise ValueError("Acceptance contains duplicate decoded content")
    previous=[]
    for path in prior_runs:previous += _prior_records(path)
    previous_hashes={r.get("sha256") for r in previous if r.get("sha256")}
    overlaps=sorted(set(hashes)&previous_hashes)
    if overlaps:raise ValueError(f"Acceptance content overlaps previous data: {len(overlaps)} hashes")
    result={"ready":True,"acceptance_rows":len(records),"labels":Counter(r["label"] for r in records),
            "unique_content_hashes":len(set(hashes)),"previous_content_hashes":len(previous_hashes),
            "content_hash_overlap":0,"prior_run_sha256":{
                str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in prior_runs},
            "manifest_sha256":hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
            "partition_independence":"Official ASVspoof5 train/dev/eval partition metadata uses disjoint speakers; exact content hashes were additionally compared here.",
            "scope_note":"Acceptance3 includes unseen evaluation attacks A17-A32 and codecs; performance is public-corpus evidence, not sponsor-distribution accuracy."}
    Path(output).write_text(json.dumps(result,indent=2)+"\n")
    return result

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("manifest",type=Path);p.add_argument("--dataset-root",type=Path,required=True)
    p.add_argument("--prior-run",type=Path,action="append",required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args(argv)
    try:print(json.dumps(run(a.manifest,a.dataset_root,a.prior_run,a.output)))
    except (OSError,ValueError) as e:print(f"INDEPENDENCE AUDIT: {e}");return 2
    return 0
if __name__=="__main__":raise SystemExit(main())
