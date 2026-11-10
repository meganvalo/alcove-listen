/* m4b.js: a small MP4/M4B metadata reader. Reads only the moov box (plus chapter text samples),
   so even a 1 GB audiobook is parsed in milliseconds. Returns {title, author, dur, cover, chapters:[{t, title}]}. */
(function (g) {
const u4 = (d, o) => String.fromCharCode(d.getUint8(o), d.getUint8(o + 1), d.getUint8(o + 2), d.getUint8(o + 3));
function kids(d, s, e) {
  const out = [];
  while (s + 8 <= e) {
    let z = d.getUint32(s), hl = 8;
    if (z === 1) { z = Number(d.getBigUint64(s + 8)); hl = 16; } else if (z === 0) z = e - s;
    if (z < hl) break;
    out.push({ t: u4(d, s + 4), s: s + hl, e: Math.min(s + z, e) });
    s += z;
  }
  return out;
}
const find = (d, b, t) => b && kids(d, b.s, b.e).find(k => k.t === t);
const path = (d, b, ...ts) => { for (const t of ts) b = find(d, b, t); return b; };
const dec = (buf, s, e, enc) => new TextDecoder(enc || 'utf-8').decode(new Uint8Array(buf, s, e - s));

async function parseM4B(file) {
  let pos = 0, moov = null;
  while (pos + 8 <= file.size) {
    const h = new DataView(await file.slice(pos, pos + 16).arrayBuffer());
    let z = h.getUint32(0), hl = 8;
    const t = u4(h, 4);
    if (z === 1 && h.byteLength >= 16) { z = Number(h.getBigUint64(8)); hl = 16; } else if (z === 0) z = file.size - pos;
    if (t === 'moov') { moov = await file.slice(pos + hl, pos + z).arrayBuffer(); break; }
    if (z < 8) break;
    pos += z;
  }
  if (!moov) throw new Error('not an mp4 file');
  const d = new DataView(moov), root = { s: 0, e: moov.byteLength }, out = { chapters: [] };

  const mv = find(d, root, 'mvhd');
  if (mv) {
    const v = d.getUint8(mv.s), ts = d.getUint32(mv.s + (v ? 20 : 12));
    out.dur = (v ? Number(d.getBigUint64(mv.s + 24)) : d.getUint32(mv.s + 16)) / ts;
  }

  // tags and cover art
  const meta = path(d, root, 'udta', 'meta') || find(d, root, 'meta');
  const il = meta && kids(d, meta.s + 4, meta.e).find(k => k.t === 'ilst');
  const tag = {};
  if (il) for (const it of kids(d, il.s, il.e)) {
    const dt = find(d, it, 'data');
    if (!dt) continue;
    const fl = d.getUint32(dt.s) & 0xffffff;
    if (it.t === 'covr') { if (!out.cover) out.cover = new Blob([moov.slice(dt.s + 8, dt.e)], { type: fl === 14 ? 'image/png' : 'image/jpeg' }); }
    else if (fl === 1) tag[it.t] = dec(moov, dt.s + 8, dt.e);
  }
  out.title = tag['\u00a9nam'] || tag['\u00a9alb'];
  out.author = tag['\u00a9ART'] || tag['aART'] || tag['\u00a9wrt'];

  // chapters, style 1: Nero "chpl" atom
  const ch = path(d, root, 'udta', 'chpl');
  if (ch) {
    let p = ch.s + (d.getUint8(ch.s) ? 8 : 4);
    const n = d.getUint8(p++);
    for (let i = 0; i < n && p + 9 <= ch.e; i++) {
      const t = Number(d.getBigUint64(p)) / 1e7; p += 8;
      const l = d.getUint8(p++);
      out.chapters.push({ t, title: dec(moov, p, p + l) }); p += l;
    }
  }

  // chapters, style 2: QuickTime chapter track (tref/chap points at a text track)
  if (!out.chapters.length) {
    const traks = kids(d, root.s, root.e).filter(k => k.t === 'trak');
    for (const tr of traks) {
      const cp = path(d, tr, 'tref', 'chap');
      if (!cp) continue;
      const id = d.getUint32(cp.s);
      const tg = traks.find(k => { const h = find(d, k, 'tkhd'); return h && d.getUint32(h.s + (d.getUint8(h.s) ? 20 : 12)) === id; });
      if (!tg) continue;
      const mh = path(d, tg, 'mdia', 'mdhd'), st = path(d, tg, 'mdia', 'minf', 'stbl');
      if (!mh || !st) continue;
      const ts = d.getUint32(mh.s + (d.getUint8(mh.s) ? 20 : 12));
      const stts = find(d, st, 'stts'), stsz = find(d, st, 'stsz'), stsc = find(d, st, 'stsc');
      const co = find(d, st, 'stco') || find(d, st, 'co64');
      if (!stts || !stsz || !stsc || !co) continue;
      const times = []; let acc = 0, p = stts.s + 8;
      for (let i = 0, n = d.getUint32(stts.s + 4); i < n; i++, p += 8) {
        const c = d.getUint32(p), dl = d.getUint32(p + 4);
        for (let k = 0; k < c; k++) { times.push(acc); acc += dl; }
      }
      const fixed = d.getUint32(stsz.s + 4), N = d.getUint32(stsz.s + 8), sizes = [];
      for (let i = 0; i < N; i++) sizes.push(fixed || d.getUint32(stsz.s + 12 + i * 4));
      const runs = []; p = stsc.s + 8;
      for (let i = 0, n = d.getUint32(stsc.s + 4); i < n; i++, p += 12) runs.push({ first: d.getUint32(p), per: d.getUint32(p + 4) });
      const nc = d.getUint32(co.s + 4), big = co.t === 'co64', samples = [];
      let r = 0, si = 0;
      for (let ci = 0; ci < nc; ci++) {
        while (r + 1 < runs.length && runs[r + 1].first <= ci + 1) r++;
        let off = big ? Number(d.getBigUint64(co.s + 8 + ci * 8)) : d.getUint32(co.s + 8 + ci * 4);
        for (let k = 0; k < runs[r].per && si < N; k++, si++) { samples.push({ off, size: sizes[si] }); off += sizes[si]; }
      }
      const parts = await Promise.all(samples.map(async s => new Uint8Array(await file.slice(s.off, s.off + s.size).arrayBuffer())));
      parts.forEach((u, i) => {
        if (u.length < 2) return;
        const b = u.subarray(2, 2 + ((u[0] << 8) | u[1]));
        const txt = b[0] === 0xfe && b[1] === 0xff ? new TextDecoder('utf-16be').decode(b.subarray(2))
          : b[0] === 0xff && b[1] === 0xfe ? new TextDecoder('utf-16le').decode(b.subarray(2))
          : new TextDecoder().decode(b);
        out.chapters.push({ t: times[i] / ts, title: txt.trim() });
      });
      break;
    }
  }
  out.chapters.sort((a, b) => a.t - b.t);
  out.chapters.forEach((c, i) => { if (!c.title) c.title = 'Chapter ' + (i + 1); });
  return out;
}
g.parseM4B = parseM4B;
if (typeof module !== 'undefined') module.exports = parseM4B;
})(typeof window !== 'undefined' ? window : globalThis);
