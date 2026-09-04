#!/usr/bin/env python3
"""Doc2Vec (100-d) + UMAP of the Harvard MGH EEG reports, colored by the reading neurologist,
to see whether authors separate into clusters — the same idea as Alexander's FH pipeline
(catvasily/eegfhabrainage), with two adaptations for Harvard:

  * the physician label is not in a DB column here; we take it from the report's signature
    ("I (XYZ) have reviewed …"), keeping the reports whose de-identification left the reader's
    initials in place (almost all at MGH);
  * because that signature is *in the text*, we strip it before training, so the clustering
    reflects writing style, not a literal name leak;
  * low-dim embedding is UMAP (as requested) rather than the t-SNE Alexander used.

Doc2Vec hyper-parameters mirror his proc_input.json (vector_size 100, window 5, epochs 100,
min_count 3, hs 1, negative 5, dm 1 / PV-DM). We train on ALL MGH reports (his all_doc2vec.model
approach) and visualize the labelled subset.

Run:  python -m analysis.harvard_doc2vec_authors
Outputs: reports/figures/harvard_doc2vec_umap.png and results/harvard/doc2vec_umap.csv
"""
from __future__ import annotations

import json
import os
import re
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.parsing.preprocessing import STOPWORDS
from gensim.utils import simple_preprocess
import umap
from sklearn.metrics import silhouette_score
from sklearn.model_selection import cross_val_score
from sklearn.neighbors import KNeighborsClassifier

from analysis.full_lib import INK, INK2, GRID

COHORT = "MGH"
MIN_REPORTS = 40           # authors with at least this many reports enter the plot
SEED = 1234321
D2V = dict(vector_size=100, window=5, epochs=100, min_count=3, hs=1, negative=5,
           ns_exponent=0.75, dm=1, dm_mean=0, dbow_words=0, dm_concat=0, seed=SEED, workers=8)
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)

# STRIP_SIG=0 keeps the signature (Alexander's literal no-strip pipeline / leakage control);
# default 1 removes it so the clustering reflects writing style, not the literal initials.
STRIP_SIG = os.environ.get("STRIP_SIG", "1") != "0"
TAG = "" if STRIP_SIG else "_nostrip"

# signature: "I (ADL) have reviewed …" -> the author token; and the sentence to strip out
SIG = re.compile(r"I \(([A-Za-z]{2,4})\)\s*(?:have|reviewed|personally|performed)", re.I)
STRIP = re.compile(r"I \([^)]{1,60}\)[^.]{0,250}\.", re.I)


def load(cohort):
    """(report_id -> stripped text), and (report_id -> author) for reports with legible initials."""
    idx = json.load(open(f"results/harvard/{cohort}_index.json"))
    zips = idx["zips"]; zc = {}
    texts, authors = {}, {}
    for rid, zi, inner in idx["reports"]:
        try:
            if zi not in zc:
                zc[zi] = zipfile.ZipFile(zips[zi])
            raw = " ".join(zc[zi].open(inner).read().decode("utf-8", "replace").split())
        except Exception:  # noqa: BLE001
            continue
        m = SIG.search(raw)
        if m:
            authors[rid] = m.group(1).upper()
        texts[rid] = STRIP.sub(" ", raw) if STRIP_SIG else raw
    return texts, authors


def tokens(text):
    return [w for w in simple_preprocess(text, deacc=False, min_len=2, max_len=15)
            if w not in STOPWORDS]


def main():
    texts, authors = load(COHORT)
    keep = {a for a, n in Counter(authors.values()).items() if n >= MIN_REPORTS}
    labelled = {rid: a for rid, a in authors.items() if a in keep}
    print(f"{COHORT}: {len(texts)} reports total; {len(authors)} with initials; "
          f"{len(labelled)} in {len(keep)} authors (>= {MIN_REPORTS}): "
          f"{', '.join(sorted(keep))}")

    # train Doc2Vec on ALL reports (tags = report_id), mirroring the all_doc2vec.model approach
    docs = [TaggedDocument(tokens(t), [rid]) for rid, t in texts.items()]
    docs = [d for d in docs if d.words]
    print(f"training Doc2Vec on {len(docs)} docs ...", flush=True)
    model = Doc2Vec(docs, **D2V)

    # vectors for ALL reports (tags are report_ids) -> UMAP the whole set, once
    all_rids = [d.tags[0] for d in docs]
    Xall = np.vstack([model.dv[r] for r in all_rids])
    y_all = np.array([labelled.get(r) for r in all_rids], dtype=object)
    print(f"UMAP on all {len(all_rids)} reports ...", flush=True)
    emb = umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.1, metric="cosine",
                    random_state=SEED).fit_transform(Xall)

    lab = np.array([a is not None for a in y_all])
    Xlab = Xall[lab]; ylab = y_all[lab].astype(str)
    sil = silhouette_score(Xlab, ylab, metric="cosine")
    knn = cross_val_score(KNeighborsClassifier(5, metric="cosine"), Xlab, ylab, cv=5).mean()
    base = Counter(ylab).most_common(1)[0][1] / len(ylab)
    print(f"labelled {len(ylab)} in {len(set(ylab))} authors | silhouette (cosine) = {sil:.3f} "
          f"| 5-NN author accuracy = {100*knn:.1f}% (majority baseline {100*base:.1f}%)")

    with open(f"results/harvard/doc2vec_umap{TAG}.csv", "w") as f:
        f.write("report_id,author,umap_x,umap_y\n")
        for r, a, (x, yy) in zip(all_rids, y_all, emb):
            f.write(f"{r},{a if a else ''},{x:.4f},{yy:.4f}\n")

    order = [a for a, _ in Counter(ylab).most_common()]
    cmap = plt.get_cmap("tab10")
    col = {a: cmap(i % 10) for i, a in enumerate(order)}

    def _frame(ax, title, sub):
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(GRID)
        ax.legend(frameon=False, fontsize=8.5, loc="center left", bbox_to_anchor=(1.0, 0.5),
                  title="reading neurologist", title_fontsize=9)
        ax.set_title(title, color=INK, fontsize=13.5, fontweight="bold", loc="left", pad=40)
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")

    sig_note = "signature removed" if STRIP_SIG else "signature KEPT (leakage control)"
    sub = (f"Doc2Vec (100-d, {sig_note}) → UMAP · silhouette {sil:.2f} · "
           f"5-NN author accuracy {100*knn:.0f}% vs {100*base:.0f}% baseline")

    # PLOT 1 — ALL reports (grey) with the 8 authors highlighted on top
    fig, ax = plt.subplots(figsize=(9.8, 7.4))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    ax.scatter(emb[~lab, 0], emb[~lab, 1], s=3, alpha=0.10, color="#c9d1dc",
               edgecolors="none", label=f"unlabelled (n={(~lab).sum():,})")
    for a in order:
        m = y_all == a
        ax.scatter(emb[m, 0], emb[m, 1], s=12, alpha=0.75, color=col[a],
                   label=f"{a} (n={m.sum()})", edgecolors="none")
    _frame(ax, "Do the reports cluster?  all MGH reports (55,557)", sub)
    fig.tight_layout()
    fig.savefig(OUT / f"harvard_doc2vec_umap_all{TAG}.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved reports/figures/harvard_doc2vec_umap_all.png")

    # PLOT 2 — plain black dots, all reports (raw cluster structure, no author overlay)
    fig, ax = plt.subplots(figsize=(8.4, 8.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    ax.scatter(emb[:, 0], emb[:, 1], s=3, alpha=0.15, color="black", edgecolors="none")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#cccccc")
    ax.set_title(f"MGH EEG reports (n={len(all_rids):,}) — Doc2Vec → UMAP",
                 fontsize=13, loc="left", color="black", pad=12)
    fig.tight_layout()
    fig.savefig(OUT / "harvard_doc2vec_umap_bw.png", bbox_inches="tight", facecolor="white", dpi=150)
    plt.close(fig)
    print("saved reports/figures/harvard_doc2vec_umap_bw.png")


if __name__ == "__main__":
    main()
