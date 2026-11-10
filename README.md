# alcove. listen

A small, private audiobook player for `.m4b` files that runs entirely in your browser. A companion to [alcove.](../alcove), with the same look. No app store, no account, no server.

## Features
- Import `.m4b` (also `.m4a` and `.mp3`) from your device, several at once
- Reads the title, author, cover art and **chapters** straight from the file (both Nero `chpl` and QuickTime chapter tracks)
- Position saved every 5 seconds and whenever you pause or leave, so you always resume where you were
- Skip back 15 s / forward 30 s, previous / next chapter, chapter list
- Speed 0.8x to 3x with pitch correction
- Sleep timer (15, 30, 45, 60 minutes, or end of chapter)
- Lock screen and headphone controls with cover art (Media Session)
- Same themes as alcove.; works offline once loaded
- Save your place to a small file and restore it on another device

## Install (host it yourself)
1. Create a repository (for example `alcove-listen`) and upload **everything in this folder** to its root.
2. **Settings → Pages**: Deploy from a branch, `main`, `/ (root)`.
3. Open `https://YOUR-USERNAME.github.io/alcove-listen/`.
4. iPhone/iPad: open in **Safari**, Share, **Add to Home Screen**. Android/desktop: use the browser's Install option.

**Add your audiobooks after installing.** On iOS the Home Screen app and Safari keep separate storage.

## Your data
Audiobooks, covers and positions are stored in your browser (IndexedDB and localStorage) on that device only. Nothing is uploaded. Nothing syncs between devices, so keep your original files. Settings, then "save my place to a file" lets you carry your position to another device that has the same books.

## Files
`index.html` (the app), `m4b.js` (metadata and chapter reader), `sw.js` (offline), `manifest.json`, `oblata.woff`, icons.

## Credits
Wordmark font: Oblata Display by Astrid Schäfer, SIL Open Font License 1.1 (same file alcove. embeds).
