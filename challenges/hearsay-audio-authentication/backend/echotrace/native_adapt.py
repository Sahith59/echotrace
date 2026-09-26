"""Bounded fine-tuning of the pinned native wav2vec2 detector."""
from __future__ import annotations

import argparse, hashlib, json, math, random, time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch.nn.utils import clip_grad_norm_
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification, get_linear_schedule_with_warmup

from .acceptance import select_threshold, summarize
from .audio import decode_audio
from .evaluation import load_manifest
from .native_detector_eval import DEFAULT_CACHE, MODEL_REVISION, WEIGHTS_SHA256, verify
from .pipeline import _windows

SEED=20260926
CONFIG={"seed":SEED,"epochs":3,"max_optimizer_steps":2000,"batch_size":4,
        "gradient_accumulation":4,"effective_batch_size":16,"learning_rate":1e-5,
        "weight_decay":.01,"warmup_steps":100,"gradient_clip_norm":1.0,
        "max_fit_seconds":9000,"feature_encoder":"frozen","precision":"fp16",
        "selection_metric":"recall_at_fpr_lte_0.05_then_roc_auc","early_stopping_patience":1,
        "window_samples":64600}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def public(records):
    keys=("file_id","sha256","label","group_id","speaker_id","source_id")
    return [{k:r.get(k,"") for k in keys} for r in records]

def load_windows(records):
    result=[]
    for i,r in enumerate(records,1):
        samples,_=decode_audio(Path(r["path"]))
        windows=[w for _,_,w in _windows(samples)]
        result.append((r["label"],windows))
        if i%500==0: print(f"decoded {i}/{len(records)}",flush=True)
    return result

def batches(items,size,shuffle,rng):
    order=list(range(len(items)))
    if shuffle:rng.shuffle(order)
    for i in range(0,len(order),size): yield [items[j] for j in order[i:i+size]]

def _optimizer_update(scaler,optimizer,scheduler,params):
    scaler.unscale_(optimizer)
    clip_grad_norm_(params,CONFIG["gradient_clip_norm"],error_if_nonfinite=True)
    scaler.step(optimizer)
    scaler.update()
    optimizer.zero_grad(set_to_none=True)
    scheduler.step()

def evaluate(items,extractor,model,device):
    labels=[];scores=[]
    model.eval()
    with torch.inference_mode():
        for group in batches(items,CONFIG["batch_size"],False,random.Random(0)):
            # Selection score keeps the production mean-over-all-windows contract.
            for label,windows in group:
                inputs=extractor(windows,sampling_rate=16000,return_tensors="pt",padding=True)
                inputs={k:v.to(device) for k,v in inputs.items()}
                with torch.autocast("cuda",dtype=torch.float16): logits=model(**inputs).logits
                score=float(torch.softmax(logits.float(),-1)[:,1].mean().cpu())
                labels.append(label);scores.append(score)
    threshold=select_threshold(labels,scores,max_fpr=.05)
    metrics=summarize(labels,scores,threshold)
    return {"threshold":threshold,"recall":metrics["recall"],
            "false_positive_rate":metrics["false_positive_rate"],
            "roc_auc":float(roc_auc_score(labels,scores))}

def run(train_manifest,selection_manifest,dataset_root,output,cache=DEFAULT_CACHE):
    output=Path(output)
    if output.exists() or output.is_symlink(): raise ValueError("Output must be fresh")
    if not torch.cuda.is_available(): raise RuntimeError("CUDA is required")
    torch.manual_seed(SEED);np.random.seed(SEED);random.seed(SEED)
    verify(cache)
    train=load_manifest(Path(train_manifest),Path(dataset_root)); selection=load_manifest(Path(selection_manifest),Path(dataset_root))
    if len(train)!=10000 or len(selection)!=2000: raise ValueError("Expected frozen 10000/2000 train/selection")
    # Existing split validator/provenance guarantees are preserved by exact manifests.
    train_data=load_windows(train);selection_data=load_windows(selection)
    extractor=AutoFeatureExtractor.from_pretrained(cache,local_files_only=True,trust_remote_code=False)
    model=AutoModelForAudioClassification.from_pretrained(cache,local_files_only=True,
            trust_remote_code=False,use_safetensors=True).to("cuda")
    if model.config.label2id!={"fake":1,"real":0}:raise RuntimeError("Label polarity changed")
    model.freeze_feature_encoder()
    params=[p for p in model.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(params,lr=CONFIG["learning_rate"],weight_decay=CONFIG["weight_decay"])
    scheduler=get_linear_schedule_with_warmup(optimizer,CONFIG["warmup_steps"],CONFIG["max_optimizer_steps"])
    scaler=torch.amp.GradScaler("cuda")
    output.mkdir(parents=True)
    started=time.monotonic();deadline=started+CONFIG["max_fit_seconds"]
    step=0;best=None;bad=0;history=[];rng=random.Random(SEED)
    for epoch in range(1,CONFIG["epochs"]+1):
        model.train();optimizer.zero_grad(set_to_none=True)
        for micro,group in enumerate(batches(train_data,CONFIG["batch_size"],True,rng),1):
            # One deterministic window per file per epoch; almost all frozen clips have one.
            waves=[windows[(epoch-1)%len(windows)] for _,windows in group]
            labels=torch.tensor([label for label,_ in group],device="cuda")
            inputs=extractor(waves,sampling_rate=16000,return_tensors="pt",padding=True)
            inputs={k:v.to("cuda") for k,v in inputs.items()}
            with torch.autocast("cuda",dtype=torch.float16):
                loss=model(**inputs,labels=labels).loss/CONFIG["gradient_accumulation"]
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite loss at epoch {epoch}, microbatch {micro}")
            scaler.scale(loss).backward()
            if micro%CONFIG["gradient_accumulation"]==0 or micro==math.ceil(len(train_data)/CONFIG["batch_size"]):
                _optimizer_update(scaler,optimizer,scheduler,params);step+=1
                if step == 1 or step % 100 == 0:
                    print(json.dumps({"event":"optimizer_step","epoch":epoch,"optimizer_step":step,
                                      "finite_loss":True,"scaled_microbatch_loss":float(loss.detach().cpu())}),flush=True)
            if step>=CONFIG["max_optimizer_steps"] or time.monotonic()>=deadline:break
        metrics=evaluate(selection_data,extractor,model,"cuda");metrics.update(epoch=epoch,optimizer_step=step)
        history.append(metrics);print(json.dumps(metrics),flush=True)
        rank=(metrics["recall"],metrics["roc_auc"])
        if best is None or rank>(best[0],best[1]):
            best=(rank[0],rank[1],epoch);bad=0
            model.save_pretrained(output/"best",safe_serialization=True)
            extractor.save_pretrained(output/"best")
            print(json.dumps({"event":"checkpoint_saved","epoch":epoch,
                              "weights_sha256":sha(output/"best/model.safetensors")}),flush=True)
        else: bad+=1
        if bad>=CONFIG["early_stopping_patience"] or step>=CONFIG["max_optimizer_steps"] or time.monotonic()>=deadline:break
    weights=output/"best/model.safetensors"
    provenance={"base":{"revision":MODEL_REVISION,"weights_sha256":WEIGHTS_SHA256},
                "adapted_weights_sha256":sha(weights),"config":CONFIG,"history":history,
                "best_epoch":best[2],"optimizer_steps":step,
                "elapsed_seconds":round(time.monotonic()-started,3),
                "split_provenance":{"train":public(train),"validation":public(selection)}}
    (output/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    return provenance

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("--train",type=Path,required=True);p.add_argument("--selection",type=Path,required=True)
    p.add_argument("--dataset-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--cache",type=Path,default=DEFAULT_CACHE)
    a=p.parse_args(argv)
    try:
        result=run(a.train,a.selection,a.dataset_root,a.output,a.cache)
        summary={key:result[key] for key in ("best_epoch","optimizer_steps","adapted_weights_sha256","elapsed_seconds")}
        print(json.dumps(summary))
    except (OSError,ValueError,RuntimeError) as e: print(f"NATIVE ADAPT: {e}");return 2
    return 0
if __name__=="__main__":raise SystemExit(main())
