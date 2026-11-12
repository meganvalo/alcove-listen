#!/usr/bin/env python3
"""
alcove-sync: build a follow-along sync file for alcove.

  1. In alcove, open the book, tap the headphones button, and choose
     "prepare text for follow-along". Save the .alcove-align.json file it makes.
  2. Run:   python make_sync.py  MyBook.alcove-align.json  MyBook.m4b
  3. In alcove, choose "import follow-along file" and pick the .alcove-sync.json it writes.

How it works: the audiobook is transcribed with Whisper (word timestamps), then the transcript is
matched against the book's sentences with a patience-diff style alignment, which tolerates
transcription mistakes, unspoken front matter and narrator extras. Everything runs on your computer.
"""
import argparse, bisect, json, os, re, sys, time

TOK = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
def toks(s):
    return TOK.findall(s.lower().replace('\u2019', "'").replace('\u2018', "'"))

# ---------------------------------------------------------------- book side
def load_book(path):
    d = json.load(open(path, encoding='utf-8'))
    if d.get('format') != 'alcove-align':
        sys.exit('That is not an alcove .alcove-align.json file.')
    words, sents = [], []          # sents: (chapter, start, end, first word index)
    for ch in d['chapters']:
        for s, e, say in ch['sents']:
            t = toks(say)
            if t:
                sents.append((ch['i'], s, e, len(words)))
                words.extend(t)
    return d, words, sents

# ---------------------------------------------------------------- alignment
K_STEPS = (8, 5, 3, 2, 1)

def _lis(pairs):
    """Longest strictly increasing run of b over pairs sorted by a (patience sorting)."""
    tails, tail_idx, prev = [], [], [-1] * len(pairs)
    for n, (_, b) in enumerate(pairs):
        j = bisect.bisect_left(tails, b)
        if j == len(tails):
            tails.append(b); tail_idx.append(n)
        else:
            tails[j] = b; tail_idx[j] = n
        prev[n] = tail_idx[j - 1] if j else -1
    out, n = [], tail_idx[-1] if tail_idx else -1
    while n >= 0:
        out.append(pairs[n]); n = prev[n]
    return out[::-1]

def _anchors(A, B, alo, ahi, blo, bhi, k):
    if ahi - alo < k or bhi - blo < k:
        return []
    def uniq(seq, lo, hi):
        d = {}
        for i in range(lo, hi - k + 1):
            g = tuple(seq[i:i + k])
            d[g] = -1 if g in d else i
        return d
    da, db = uniq(A, alo, ahi), uniq(B, blo, bhi)
    pairs = sorted((i, db[g]) for g, i in da.items() if i >= 0 and db.get(g, -1) >= 0)
    out, la, lb = [], -1, -1
    for a, b in _lis(pairs):
        for j in range(k):
            if a + j > la and b + j > lb:
                out.append((a + j, b + j)); la, lb = a + j, b + j
    return out

def align(A, B):
    """Match transcript words A to book words B. Returns sorted [(a_index, b_index)]."""
    matches, stack = [], [(0, len(A), 0, len(B), 0)]
    while stack:
        alo, ahi, blo, bhi, ki = stack.pop()
        if ki >= len(K_STEPS) or alo >= ahi or blo >= bhi:
            continue
        if K_STEPS[ki] <= 2:
            # weak (1-2 word) matches are only trusted when both sides are of similar size;
            # otherwise random transcription junk can coincidentally match unspoken text
            r = (ahi - alo) / (bhi - blo)
            if not 0.4 <= r <= 2.5 or max(ahi - alo, bhi - blo) > 400:
                continue
        anc = _anchors(A, B, alo, ahi, blo, bhi, K_STEPS[ki])
        if not anc:
            stack.append((alo, ahi, blo, bhi, ki + 1)); continue
        matches += anc
        pa, pb = alo, blo
        for a, b in anc + [(ahi, bhi)]:
            if a > pa and b > pb:
                stack.append((pa, a, pb, b, ki + 1))
            pa, pb = a + 1, b + 1
    matches.sort()
    return matches

# ---------------------------------------------------------------- times
WPS_LO, WPS_HI, WPS_TYP = 0.8, 5.5, 2.6    # plausible speech rate (words per second)

def sentence_times(nwords, sents, matches, a_start):
    """Start time for each sentence, or None when it cannot be placed with confidence."""
    mb = [b for _, b in matches]
    mt = [a_start[a] for a, _ in matches]
    def time_at(w):
        j = bisect.bisect_left(mb, w)
        if j < len(mb) and mb[j] == w:
            return mt[j]
        pb, pt = (mb[j - 1], mt[j - 1]) if j else (None, None)
        nb, nt = (mb[j], mt[j]) if j < len(mb) else (None, None)
        if pb is not None and nb is not None:
            sec, wd = nt - pt, nb - pb
            if sec > 0 and WPS_LO <= wd / sec <= WPS_HI:
                return pt + (w - pb) * sec / wd
            if w - pb <= 15: return pt + (w - pb) / WPS_TYP
            if nb - w <= 15: return nt - (nb - w) / WPS_TYP
            return None
        if pb is not None and w - pb <= 15: return pt + (w - pb) / WPS_TYP
        if nb is not None and nb - w <= 15: return max(0.0, nt - (nb - w) / WPS_TYP)
        return None
    out, last = [], 0.0
    for _, _, _, w0 in sents:
        t = time_at(w0)
        if t is not None:
            t = max(t, last); last = t
        out.append(t)
    return out

# ---------------------------------------------------------------- speech recognition
def transcribe(audio, model_name, lang, cache):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit('Please install the speech engine first:   pip install faster-whisper')
    print(f'Loading Whisper model "{model_name}" (downloads once)...')
    model = WhisperModel(model_name, device='auto', compute_type='auto')
    segs, info = model.transcribe(audio, language=lang, word_timestamps=True, vad_filter=True,
                                  condition_on_previous_text=False, beam_size=1)
    words, t0 = [], time.time()
    try:
        for sg in segs:
            for w in (sg.words or []):
                words.append([w.word.strip(), round(w.start, 2), round(w.end, 2)])
            done = sg.end / max(1, info.duration)
            el = time.time() - t0
            print(f'\r  transcribing {done * 100:5.1f}%   elapsed {el / 60:5.1f} min' +
                  (f'   about {(el / done - el) / 60:5.1f} min left' if done > .01 else ''), end='', flush=True)
    except KeyboardInterrupt:
        print('\nStopped early. Keeping what was transcribed so far.')
    print()
    json.dump({'words': words, 'duration': info.duration}, open(cache, 'w'))
    return words

def load_transcript(path):
    d = json.load(open(path, encoding='utf-8'))
    return d['words'] if isinstance(d, dict) else d

# ---------------------------------------------------------------- main
def build(book_path, words_in):
    d, B, sents = load_book(book_path)
    A, a_start = [], []
    for w, s, *_ in words_in:
        for t in toks(w):
            A.append(t); a_start.append(float(s))
    m = align(A, B)
    times = sentence_times(len(B), sents, m, a_start)
    chapters = {}
    for (ci, s, e, _), t in zip(sents, times):
        if t is not None:
            chapters.setdefault(ci, []).append([s, e, round(t, 2)])
    lens = {c['i']: c['len'] for c in d['chapters']}
    total, synced = len(sents), sum(len(v) for v in chapters.values())
    out = {'format': 'alcove-sync', 'v': 1, 'book': d.get('book', {}),
           'audio': {'dur': round(a_start[-1], 1) if a_start else 0},
           'chapters': [{'i': i, 'len': lens.get(i, 0), 's': v} for i, v in sorted(chapters.items())],
           'stats': {'sentences': total, 'synced': synced, 'matched_words': len(m), 'book_words': len(B)}}
    return out, d

def main():
    ap = argparse.ArgumentParser(description='Build an alcove follow-along sync file.')
    ap.add_argument('align', help='the .alcove-align.json file exported from alcove')
    ap.add_argument('audio', nargs='?', help='the audiobook (m4b, mp4, m4a, mp3...)')
    ap.add_argument('-o', '--out', help='output file (default: next to the audiobook)')
    ap.add_argument('--model', default='small.en', help='Whisper model: tiny.en, base.en, small.en (default), medium.en; drop ".en" for other languages')
    ap.add_argument('--lang', default='en', help='language code (default en)')
    ap.add_argument('--transcript', help='use an existing transcript .json instead of running Whisper')
    a = ap.parse_args()
    if a.transcript:
        words = load_transcript(a.transcript)
    else:
        if not a.audio: ap.error('give the audiobook file, or --transcript')
        cache = a.audio + '.transcript.json'
        if os.path.exists(cache):
            print('Reusing', cache); words = load_transcript(cache)
        else:
            words = transcribe(a.audio, a.model, a.lang, cache)
    print(f'{len(words):,} spoken words found. Aligning...')
    out, d = build(a.align, words)
    st = out['stats']
    pct = 100 * st['synced'] / max(1, st['sentences'])
    base = (a.audio or a.align)
    path = a.out or re.sub(r'(\.alcove-align)?\.[^.]+$', '', base) + '.alcove-sync.json'
    json.dump(out, open(path, 'w'), separators=(',', ':'))
    print(f'Synced {st["synced"]:,} of {st["sentences"]:,} sentences ({pct:.0f}%). Wrote {path}')
    weak = [c['i'] for c in d['chapters'] if len(c['sents']) > 5 and
            sum(len(x['s']) for x in out['chapters'] if x['i'] == c['i']) < 0.5 * len(c['sents'])]
    if weak: print('Chapters with weak coverage (often front/back matter that is not narrated):', weak[:20])
    if pct < 60: print('Low coverage: the audiobook may be a different edition or abridged, or try a larger --model.')

if __name__ == '__main__':
    main()
