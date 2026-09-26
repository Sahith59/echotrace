"""Content-level independence audit for a locked acceptance manifest."""
from __future__ import annotations
import argparse, csv, hashlib, json, re
from collections import Counter
from pathlib import Path

def _acceptance_records(manifest,dataset_root):
    with Path(manifest).open(encoding="utf-8",newline="") as handle:
        rows=list(csv.DictReader(handle))
    records=[]
    root=Path(dataset_root).resolve()
    for row in rows:
        path=(root/row["path"]).resolve()
        if root not in path.parents or not path.is_file():raise ValueError(f"Invalid acceptance audio path: {row['path']}")
        with path.open("rb") as source:digest=hashlib.file_digest(source,"sha256").hexdigest()
        records.append({**row,"label":int(row["label"]),"sha256":digest})
    return records

def _prior_ledger(run):
    data=json.loads(Path(run).read_text())
    records=list(data.get("records") or [])
    provenance=data.get("training_provenance") or {}
    train=list(provenance.get("train") or [])
    validation=list(provenance.get("validation") or [])
    return {"records":records,"train":train,"validation":validation}

def _validated_hashes(records,description):
    hashes=[]
    for index,record in enumerate(records):
        digest=record.get("sha256")
        if not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest):
            raise ValueError(f"Invalid SHA-256 in {description} at record {index}")
        hashes.append(digest)
    return hashes

def run(manifest,dataset_root,prior_runs,output):
    records=_acceptance_records(Path(manifest),Path(dataset_root))
    if len(records)!=2000 or Counter(r["label"] for r in records)!={0:1000,1:1000}:
        raise ValueError("Acceptance must be frozen at 1000 files per class")
    hashes=[r["sha256"] for r in records]
    if len(set(hashes))!=len(hashes):raise ValueError("Acceptance contains duplicate original-file bytes")
    if len(prior_runs)!=3:raise ValueError("Expected training/selection and two prior acceptance ledgers")
    previous=[];coverage={}
    for path in prior_runs:
        ledger=_prior_ledger(path)
        if not ledger["records"]:raise ValueError(f"Prior evaluation records missing: {path}")
        coverage[str(path)]={key:len(value) for key,value in ledger.items()}
        for name,items in ledger.items():
            _validated_hashes(items,f"{path}:{name}")
            previous += items
    if not any(counts["train"]==10000 and counts["validation"]==2000 for counts in coverage.values()):
        raise ValueError("Frozen 10000/2000 training and selection provenance is missing")
    previous_hashes=set(_validated_hashes(previous,"combined prior ledger"))
    overlaps=sorted(set(hashes)&previous_hashes)
    if overlaps:raise ValueError(f"Acceptance original-file bytes overlap previous data: {len(overlaps)} hashes")
    result={"ready":True,"acceptance_rows":len(records),"labels":Counter(r["label"] for r in records),
            "unique_content_hashes":len(set(hashes)),"previous_content_hashes":len(previous_hashes),
            "content_hash_scope":"SHA-256 of exact original audio-file bytes; no decoded-PCM deduplication claim",
            "content_hash_overlap":0,"prior_ledger_coverage":coverage,"prior_run_sha256":{
                str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in prior_runs},
            "manifest_sha256":hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
            "partition_independence":"Official ASVspoof5 train/dev/eval partition metadata uses disjoint speakers; exact original-file hashes were additionally compared here.",
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
