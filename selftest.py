"""Simulated end-to-end accuracy test for the aligner: ground truth vs. a noisy fake transcript."""
import random, json, statistics, sys, os, tempfile
SYN = os.path.join(tempfile.gettempdir(), 'syn_align.json')
sys.path.insert(0, '.')
import make_sync as ms
random.seed(7)
vocab = [''.join(random.choice('abcdefghilmnoprstuw') for _ in range(random.randint(2, 9))) for _ in range(2500)]
common = ['the', 'and', 'of', 'to', 'a', 'in', 'he', 'she', 'it', 'was', 'that', 'his', 'her', 'with']
def word(): return random.choice(common) if random.random() < .35 else random.choice(vocab)
chapters, truth, t = [], {}, 0.0
t += 25  # audiobook intro: narrator says things that are not in the book
intro = [(random.choice(vocab), 1 + i * .4) for i in range(40)]
asr = []
for w, ts in intro: asr.append([w, ts, ts + .3])
for ci in range(30):
    sents = []
    pos = 0
    if ci == 0:  # front matter that is NOT narrated
        for _ in range(20):
            text = ' '.join(word() for _ in range(8)) + '.'; sents.append([pos, pos + len(text), text]); pos += len(text) + 1
    else:
        for _ in range(random.randint(60, 140)):
            n = random.randint(5, 30); ws = [word() for _ in range(n)]
            text = ' '.join(ws) + '.'
            sents.append([pos, pos + len(text), text]); truth[(ci, pos)] = t
            for w in ws:
                dur = random.uniform(.2, .5); asr.append([w, t, t + dur]); t += dur + random.uniform(0, .08)
            pos += len(text) + 1; t += random.uniform(.2, .8)
        t += 3  # pause between chapters
    chapters.append({'i': ci, 'len': pos, 'sents': sents})
# ASR noise: 5% drops, 6% substitutions, 3% junk insertions, plus a 90 s stretch of garbage (music)
noisy = []
for w, s, e in asr:
    r = random.random()
    if r < .05: continue
    if r < .11: w = random.choice(vocab)
    noisy.append([w, s, e])
    if random.random() < .03: noisy.append([random.choice(vocab), e, e + .2])
mid = len(noisy) // 2
noisy[mid:mid] = [[random.choice(vocab), noisy[mid][1] - 0.5 + i * .1, 0] for i in range(60)]
json.dump({'format': 'alcove-align', 'chapters': chapters, 'book': {}}, open(SYN, 'w'))
out, _ = ms.build(SYN, noisy)
errs = []
for ch in out['chapters']:
    if ch['i'] == 0: continue
    for s, e, tt in ch['s']:
        errs.append(abs(tt - truth[(ch['i'], s)]))
n_true = len(truth)
errs.sort()
print(f"sentences with narration: {n_true}; synced: {len(errs)} ({100*len(errs)/n_true:.1f}%)")
print(f"median error {statistics.median(errs):.2f}s | 95th percentile {errs[int(len(errs)*.95)]:.2f}s | max {errs[-1]:.2f}s")
for lim in (.5, 1, 2): print(f"within {lim}s: {100*sum(e<=lim for e in errs)/len(errs):.1f}%")
fm = [c for c in out['chapters'] if c['i'] == 0]
print('front matter (not narrated) wrongly synced:', sum(len(c['s']) for c in fm), 'of 20')
