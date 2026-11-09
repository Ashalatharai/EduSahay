"""Field-level precision / recall / F1 (strict: a wrong value counts as both a false positive and a false negative)."""
from collections import defaultdict


def _norm(v):
    return None if v is None else " ".join(str(v).lower().split())


def field_scores(gold: list[dict], pred: list[dict]) -> dict:
    """gold/pred: one {field_name: value} dict per document."""
    c = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for g, p in zip(gold, pred):
        for name in set(g) | set(p):
            key = "subject" if name.startswith("subject_") else name
            gv, pv = _norm(g.get(name)), _norm(p.get(name))
            if gv is not None and pv == gv:
                c[key]["tp"] += 1
            else:
                if pv is not None: c[key]["fp"] += 1
                if gv is not None: c[key]["fn"] += 1

    def prf(tp, fp, fn):
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        return {"precision": pr, "recall": rc, "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0, "support": tp + fn}

    total = {k: sum(v[k] for v in c.values()) for k in ("tp", "fp", "fn")}
    return {"per_field": {k: prf(**v) for k, v in sorted(c.items())}, "micro": prf(**total)}
