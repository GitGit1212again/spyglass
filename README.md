# Spyglass

A free OSINT workspace that runs on your own computer (Windows or Mac). Type a name, company,
username, email, phone number, website, link, address, VIN or crypto wallet, or drop in a photo or
document. Spyglass guesses what it is and shows only the tools that fit. Tools marked THIS PC run
here and their results are saved in the case. Tools marked WEB open the site in your browser. Every
lookup is logged with the time in the case's history. None of the tools cost money; some sites ask
you to sign in.

"Start here" is set up for investigative research and due diligence: court records, company
registries, sanctions lists, SEC filings, Spanish-language search, news, archives, page capture,
file fingerprints and metadata. Star or unstar any tool to change it.

**Lawful use:** Spyglass only searches public-record and openly published sources; follow each
site's terms of service and the law where you live.

## Run on Windows / Run on Mac

Status: Windows 11 is tested. The Mac steps below are written for macOS but have not been run on a
Mac yet; please report anything that fails.

### Windows

1. Install Python 3.10 or newer from https://www.python.org/downloads/ (tick "Add python.exe to PATH").
2. Get this folder (clone it or download the ZIP and unzip it).
3. Double-click `Run-Spyglass.cmd`. The first time, it creates a private `.venv` and installs the
   tools from `requirements.txt` (needs internet, takes a few minutes). After that it starts at once
   and opens http://127.0.0.1:8803 in your browser.
4. Optional programs, from a Command Prompt:

       winget install OliverBetz.ExifTool
       winget install OWASP.Amass
       winget install Gyan.FFmpeg

### Mac

1. Install Python 3.10 or newer: `brew install python` (Homebrew, https://brew.sh) or the installer
   from https://www.python.org/downloads/.
2. Get this folder (clone it or download the ZIP and unzip it).
3. Open Terminal, go to the folder, and make the launcher runnable (needed once; ZIP downloads and
   Windows copies lose the executable flag):

       cd path/to/spyglass
       chmod +x Run-Spyglass.command

4. Start it: `./Run-Spyglass.command`, or double-click `Run-Spyglass.command` in Finder. If macOS says it
   is from an unidentified developer, right-click the file, choose Open, then Open (or run
   `xattr -d com.apple.quarantine Run-Spyglass.command`).
5. The first run creates the private `.venv` and installs the tools (needs internet, takes a few
   minutes), then opens http://127.0.0.1:8803 in your default browser. macOS may ask to let Terminal
   use your Documents folder, where cases are saved: choose Allow (or set `SPYGLASS_DATA`, below).
6. Optional programs:

       brew install exiftool amass ffmpeg

To do the same by hand on either system (Mac shown; on Windows use `.venv\Scripts\python.exe`):

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python server.py --open      # stops when the tab closes
    .venv/bin/python server.py --keep      # stays running until you press Ctrl+C

Spyglass stops by itself a few seconds after you close its browser tab. If a tool needs a program that
is not installed (ExifTool, Amass, ffmpeg), its card says NOT INSTALLED and shows the install command;
everything else keeps working.

## Where things live

```
server.py            web server, tool runner, case storage
catalog.py           the built-in tool list (plain-language titles) and the default "Start here" set
autoquit.py          makes the server exit when the browser page is closed
helpers/             small lookups written for Spyglass: phone, whois, DNS, VIN, page capture,
                     file fingerprint, photo location
src/                 the page (ES modules, no build step; the server serves it directly)
  js/main.js         wiring       js/detect.js   guesses what was typed
  js/ui/*.js         tool cards, results, case/notes/history, add-your-own-tool dialog
  js/data/learn.js   the LEARN tab links
tools/make_icon.py   draws assets/spyglass.ico (needs Pillow)
requirements.txt     Python packages for the private .venv
Run-Spyglass.cmd     Windows launcher        Run-Spyglass.command   Mac launcher
.venv/               private Python with the installed tools (created on first run; not in git)
```

Case data lives outside this folder, in `Documents/Spyglass/` under your home folder
(`%USERPROFILE%\Documents\Spyglass` on Windows, `~/Documents/Spyglass` on Mac). Set the
`SPYGLASS_DATA` environment variable to use another folder.
`settings.json` (stars, hidden tools, your own tools, last case) and
`cases/<case>/` with `notes.md`, `history.jsonl`, `results/` (one text file per run) and
`files/` (dropped files, page captures, downloads).

## Installed tools

Installed into `.venv` by `requirements.txt`: sherlock-project, maigret, holehe, ignorant,
instaloader, gallery-dl, yt-dlp, python-whois, dnspython, phonenumbers, certifi.
Separate programs (not on pip), used by a few tools:

| Program  | Used for                          | Windows                           | Mac                   |
|----------|-----------------------------------|-----------------------------------|-----------------------|
| ExifTool | photo and file details, GPS       | `winget install OliverBetz.ExifTool` | `brew install exiftool` |
| Amass    | sub-sites of a website            | `winget install OWASP.Amass`      | `brew install amass`  |
| ffmpeg   | joining video and audio (yt-dlp)  | `winget install Gyan.FFmpeg`      | `brew install ffmpeg` |

## Add a tool

From the page: **+ ADD YOUR OWN TOOL**. A website needs an address with `{query}` where the
search words go. A program needs a command with `{query}`; it runs in the case's files folder.
To add a built-in one, add an entry to `catalog.py`.

## Safety

Tools are started with an argument list, never through a shell, so typed text is always one
argument and may not start with `-`. The server only listens on 127.0.0.1 and only answers its
own page. Set `SPYGLASS_DRYRUN=1` to log website opens without opening tabs or windows (for testing).

## Known limits

- Sites change their pages; username and email checkers (Sherlock, Maigret, holehe) can report
  false hits or miss accounts. Open the link before relying on a hit.
- Some sites rate-limit repeated checks; wait and try again.
- "Save a dated copy of this page" saves what the server sends. Pages built by scripts or behind
  a login may save without their content; use the Wayback Machine or a screenshot for those.
- Instaloader and similar tools may keep their own login or session files in your user folder
  (outside this project) if you log them in. Those are yours; never commit them.
