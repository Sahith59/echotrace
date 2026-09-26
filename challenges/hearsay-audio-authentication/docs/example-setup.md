# Optional public example setup

ECHOTRACE includes a provenance manifest for 24 small public pilot clips: 12
genuine clips and 12 synthetic clips. The manifest pins the Hugging Face dataset
`mueller91/MLAAD-tiny` to revision
`9143e5ea709575ebab6bec52840a1043aada7bb1` and records the exact path, byte
count, and SHA-256 digest for every file. The complete bounded download is
5,274,736 bytes.

The audio is optional. The application, test suite, and CI do not download it.
To review the source terms and explicitly start the download, run this from the
backend directory:

```sh
uv run python -m echotrace.setup_examples --confirm-source-review
```

The default output is `artifacts/public-pilot/`. Use `--output PATH` to select a
different directory. The downloader accepts only the 24 URLs derived from the
checked-in dataset revision. It permits only the single HTTPS redirect that
Hugging Face uses from that pinned URL to a fixed allowlist of its delivery
hosts. It limits each file and the total catalog size, streams with a 30-second
request timeout, and verifies both the declared byte count and SHA-256 before
publishing a file. A rerun skips files that still match. It refuses to overwrite
a changed file or follow an output symlink; remove or relocate a changed file
yourself before retrying.

Review the upstream materials before downloading:

- [MLAAD-tiny dataset card](https://huggingface.co/datasets/mueller91/MLAAD-tiny)
- [Pinned M-AILABS-derived audio license file](https://huggingface.co/datasets/mueller91/MLAAD-tiny/blob/9143e5ea709575ebab6bec52840a1043aada7bb1/original/LICENSE)
- [Full MLAAD dataset card and paper citation](https://huggingface.co/datasets/mueller91/MLAAD)
- [Creative Commons Attribution-NonCommercial 4.0](https://creativecommons.org/licenses/by-nc/4.0/)
- [Hugging Face terms](https://huggingface.co/terms-of-service)

The upstream card labels MLAAD-tiny as CC BY-NC 4.0 and separately says that
the genuine audio derives from M-AILABS. Mixed source material can carry
different attribution or use conditions. The confirmation flag records only
that you reviewed the linked material and chose to download. It does not accept
or determine legal terms for you.

When publishing results based on these clips, preserve the dataset and source
attribution. The MLAAD card requests citation of:

> Müller, Nicolas M.; Kawa, Piotr; Choong, Wei Herng; Casanova, Edresson;
> Gölge, Eren; Müller, Thorsten; Syga, Piotr; Sperl, Philip; Böttinger,
> Konstantin. “MLAAD: The Multi-Language Audio Anti-Spoofing Dataset.” 2024.
> arXiv:2401.09512.
