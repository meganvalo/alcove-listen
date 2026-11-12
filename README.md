# alcove-sync

Makes the **follow-along** file for alcove. With it, alcove highlights each sentence as the narrator reads it, turns the pages for you, and lets you tap any sentence to jump the audio there.

It runs on your own computer (Mac, Windows or Linux). Nothing is uploaded anywhere.

## One-time setup
1. Install Python 3.9 or newer from python.org (Mac: it is usually already there).
2. In a terminal: `pip install faster-whisper`

## For each book
1. **In alcove**: open the book, tap the page, tap the headphones button, attach your audiobook if you have not yet, then choose **follow-along: prepare text file**. Save the `.alcove-align.json` file and get it onto your computer (AirDrop, iCloud Drive, email to yourself).
2. **On your computer**, in a terminal:

   ```
   python make_sync.py "My Book.alcove-align.json" "My Book.m4b"
   ```

   It listens to the audiobook (this is the slow part), then writes `My Book.alcove-sync.json` next to the audiobook.
3. **In alcove**: headphones button, **follow-along: import sync file**, pick the `.alcove-sync.json`. Then choose **follow along from here**.

## Good to know
- **Time:** transcribing is the slow step. It depends on your computer; as a rough guide a long audiobook can take one to a few hours on a laptop. It shows progress and time left. Press Ctrl+C to stop early and keep what was transcribed so far. The transcript is saved next to the audiobook (`.transcript.json`), so running again is instant.
- **Speed vs accuracy:** `--model base.en` is faster, `--model small.en` (default) is a good balance, `--model medium.en` is more accurate but slow. For books that are not in English, drop `.en` (for example `--model small --lang fr`).
- **First run** downloads the speech model once (about 250 MB for small.en).
- **It tolerates mistakes.** Misheard words, narrator introductions, music, and front or back matter that is not read aloud are all fine. When it finishes it prints how many sentences it placed. Over 90% is typical for a matching edition.
- **Use the same edition.** An abridged audiobook, or a different translation or edition than your ebook, will sync poorly or not at all.
- **Do not edit the ebook** after exporting. If the text differs, alcove tells you the file does not match this edition.
- The sync file stays on the device it was imported to and is not part of alcove backups. Keep the `.alcove-sync.json` if you want to import it on another device.

## Check it works
`python selftest.py` runs a built-in accuracy test with simulated recognition errors (no audio needed).

## Options
`python make_sync.py -h` lists them. Useful: `--transcript file.json` to align an existing word-timed transcript instead of running Whisper, and `-o` to choose the output file.
