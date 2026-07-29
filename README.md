# GnuLibrary

A tool for synchronizing music collections between two storage locations while maintaining full user control over every change.

## Description

GnuLibrary compares two folders (e.g., main storage and MP3 player), detects differences in files and folder structure, and presents a detailed log of all changes. It then asks for explicit user confirmation before applying any modifications to the target storage.

Key features:
- Detects new, missing, moved, renamed, and modified files
- Uses audio metadata (via Mutagen) and file hashing for accurate matching
- Supports folder reorganization detection
- Requires user approval for every action; no automatic changes
- Dry-run mode for testing without making modifications
- Multi-language support (English, Romanian, Russian)
- Single-file Python script with minimal dependencies

## Requirements

- Python 3.7 or higher
- Optional: mutagen library for enhanced metadata analysis (pip install mutagen)
- Optional: tkinter for GUI folder selection (usually included with Python)

## Usage

Run the program:

    python GnuLibrary.py

Command-line options:

    python GnuLibrary.py --dry-run      # Test without making changes
    python GnuLibrary.py --lang ro      # Start in Romanian
    python GnuLibrary.py --lang ru      # Start in Russian
    python GnuLibrary.py --no-verbose   # Reduce output verbosity
    python GnuLibrary.py --help         # Show help message

## How It Works

1. Select Source and Target: Choose two folders to compare using the built-in browser or by typing paths.
2. Scan and Compare: The program scans both locations, calculates file fingerprints, and compares metadata.
3. Review Changes: A detailed list of differences is shown (new files, missing files, moves, modifications).
4. Approve Actions: For each change, you decide whether to copy, move, delete, or skip. Batch decisions are supported.
5. Execute: Approved changes are applied to the target folder. A JSON log is saved in the target directory.

## File Matching Logic

Files are matched using:
- Partial hash (first 1MB + last 1MB) for speed and accuracy
- Audio metadata (title, artist, album, duration) if Mutagen is available
- File size comparison
- Confidence scoring to suggest matches when filenames differ

The program never assumes intent. If two files cannot be confidently matched, they are treated as separate entities, and the user decides what to do.

## Adding Translations

Translations are stored as dictionaries in the source code. To add a new language:
1. Add a new entry in the TRANSLATIONS dictionary with the language code.
2. Provide translations for all required keys.
3. Use the --lang flag to select the new language.

## License

This software is licensed under the GNU General Public License v3. See the LICENSE file for details.
