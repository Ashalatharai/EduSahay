"""Character and word error rate for OCR evaluation."""


def edit_distance(ref, hyp) -> int:
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    ref = " ".join(reference.split())
    return edit_distance(ref, " ".join(hypothesis.split())) / max(len(ref), 1)


def wer(reference: str, hypothesis: str) -> float:
    ref = reference.split()
    return edit_distance(ref, hypothesis.split()) / max(len(ref), 1)
