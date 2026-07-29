"""
GnuLibrary - High Performance Music Collection Synchronizer
License: GNU GPL v3 (See separate LICENSE file)
"""

import os
import sys
import hashlib
import json
import threading
import subprocess
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import defaultdict

# Optional: Mutagen for metadata
try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

# ==============================================================================
# CONFIGURATION & CONSTANTS
# ==============================================================================

VERSION = "1.0.0"
BUFFER_SIZE = 1024 * 1024  # 1MB chunks for hashing
HASH_PART_SIZE = 1024 * 512  # 512KB from start and end

# Supported extensions (case-insensitive)
SUPPORTED_EXTENSIONS = {
    '.mp3', '.m4a', '.mp4', '.aac', '.mpc', '.ogg', '.flac', 
    '.wav', '.wma', '.opus', '.aiff', '.dsf', '.ape', '.spx', '.tta', '.ofr'
}

# Translations
TRANSLATIONS = {
    'en': {
        'welcome': "GnuLibrary - Music Collection Synchronizer",
        'select_lang': "Available languages: en (English), ro (Română), ru (Русский)\nSelect language (en/ro/ru): ",
        'select_source': "Select SOURCE storage location:",
        'select_target': "Select TARGET storage location:",
        'enter_path': "Enter path (or type 'ls' to list current dir, 'browse' for native picker): ",
        'scanning': "Scanning {path}...",
        'found_files': "Found {count} media files.",
        'analyzing': "Analyzing fingerprints...",
        'comparing': "Comparing libraries...",
        'changes_found': "Changes detected:",
        'new_file': "[NEW] {path}",
        'missing_file': "[MISSING] {path}",
        'moved_file': "[MOVED] {src} -> {dst}",
        'modified_file': "[MODIFIED] {path}",
        'action_copy': "Copy",
        'action_delete': "Delete",
        'action_skip': "Skip",
        'action_move': "Move",
        'prompt_action': "Action (c/d/m/s)? ",
        'batch_prompt': "Apply '{action}' to all remaining similar items? (y/n): ",
        'dry_run': "*** DRY RUN MODE - NO CHANGES WILL BE MADE ***",
        'log_saved': "Log saved to: {path}",
        'error_path': "Error: Path does not exist.",
        'error_browse': "Native picker unavailable or failed.",
        'processing': "Processing: {file}",
        'hashing': "Hashing: {file}",
        'finish': "Synchronization complete.",
        'confirm_apply': "Apply these changes now? (yes/no): "
    },
    'ro': {
        'welcome': "GnuLibrary - Sincronizator Colecție Muzicală",
        'select_lang': "Limbi disponibile: en (English), ro (Română), ru (Русский)\nAlege limba (en/ro/ru): ",
        'select_source': "Alege locația SURSĂ:",
        'select_target': "Alege locația ȚINTĂ:",
        'enter_path': "Introdu calea (sau 'ls' pentru listare, 'browse' pentru selector nativ): ",
        'scanning': "Scanare {path}...",
        'found_files': "Găsite {count} fișiere media.",
        'analyzing': "Analizare amprente...",
        'comparing': "Comparare biblioteci...",
        'changes_found': "Modificări detectate:",
        'new_file': "[NOU] {path}",
        'missing_file': "[LIPSĂ] {path}",
        'moved_file': "[MUTAT] {src} -> {dst}",
        'modified_file': "[MODIFICAT] {path}",
        'action_copy': "Copiază",
        'action_delete': "Șterge",
        'action_skip': "Sari",
        'action_move': "Mută",
        'prompt_action': "Acțiune (c/d/m/s)? ",
        'batch_prompt': "Aplică '{action}' la toate elementele similare rămase? (y/n): ",
        'dry_run': "*** MOD USCAT - NICIO MODIFICARE NU VA FI FĂCUTĂ ***",
        'log_saved': "Jurnal salvat la: {path}",
        'error_path': "Eroare: Calea nu există.",
        'error_browse': "Selectorul nativ nu este disponibil.",
        'processing': "Procesare: {file}",
        'hashing': "Hashing: {file}",
        'finish': "Sincronizare completă.",
        'confirm_apply': "Aplicați aceste modificări acum? (yes/no): "
    },
    'ru': {
        'welcome': "GnuLibrary - Синхронизатор Музыкальной Коллекции",
        'select_lang': "Доступные языки: en (English), ro (Română), ru (Русский)\nВыберите язык (en/ro/ru): ",
        'select_source': "Выберите ИСХОДНОЕ хранилище:",
        'select_target': "Выберите ЦЕЛЕВОЕ хранилище:",
        'enter_path': "Введите путь (или 'ls' для списка, 'browse' для нативного выбора): ",
        'scanning': "Сканирование {path}...",
        'found_files': "Найдено файлов: {count}.",
        'analyzing': "Анализ отпечатков...",
        'comparing': "Сравнение библиотек...",
        'changes_found': "Обнаружены изменения:",
        'new_file': "[НОВЫЙ] {path}",
        'missing_file': "[ОТСУТСТВУЕТ] {path}",
        'moved_file': "[ПЕРЕМЕЩЕН] {src} -> {dst}",
        'modified_file': "[ИЗМЕНЕН] {path}",
        'action_copy': "Копировать",
        'action_delete': "Удалить",
        'action_skip': "Пропустить",
        'action_move': "Переместить",
        'prompt_action': "Действие (c/d/m/s)? ",
        'batch_prompt': "Применить '{action}' ко всем остальным похожим элементам? (y/n): ",
        'dry_run': "*** СУХОЙ ЗАПУСК - ИЗМЕНЕНИЯ НЕ БУДУТ ВНЕСЕНЫ ***",
        'log_saved': "Лог сохранен в: {path}",
        'error_path': "Ошибка: Путь не существует.",
        'error_browse': "Нативный выбор недоступен.",
        'processing': "Обработка: {file}",
        'hashing': "Хеширование: {file}",
        'finish': "Синхронизация завершена.",
        'confirm_apply': "Применить эти изменения сейчас? (yes/no): "
    }
}

# Global state
LANG = 'en'
DRY_RUN = False
VERBOSE = True

def t(key, **kwargs):
    """Translate a key."""
    text = TRANSLATIONS.get(LANG, TRANSLATIONS['en']).get(key, key)
    return text.format(**kwargs) if kwargs else text

def raw_print(msg, end='\n'):
    """Direct stdout write for maximum speed."""
    sys.stdout.write(msg + end)
    sys.stdout.flush()

# ==============================================================================
# HIGH PERFORMANCE FILE SYSTEM OPERATIONS
# ==============================================================================

def get_native_picker():
    """Attempt to open native file picker via OS commands, return path or None."""
    system = platform.system()
    try:
        if system == "Windows":
            # PowerShell command to open Folder Dialog
            cmd = '''powershell -Command "Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; $f.ShowDialog(); $f.SelectedPath"'''
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        elif system == "Darwin":
            # AppleScript for macOS
            cmd = '''osascript -e 'tell app "System Events" to choose folder' | sed 's/^alias //' '''
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        elif system == "Linux":
            # Try zenity, kdialog, or xdg-utils
            for tool in ['zenity --file-selection --directory', 'kdialog --getexistingdirectory']:
                try:
                    res = subprocess.run(tool, shell=True, capture_output=True, text=True, timeout=10)
                    if res.returncode == 0 and res.stdout.strip():
                        return res.stdout.strip().replace('file://', '')
                except:
                    continue
    except Exception:
        pass
    return None

def list_dir_fast(path):
    """Fast directory listing with extension filtering."""
    try:
        entries = os.scandir(path)
        files = []
        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False):
                    if os.path.splitext(entry.name)[1].lower() in SUPPORTED_EXTENSIONS:
                        files.append(entry.path)
                elif entry.is_dir(follow_symlinks=False):
                    # Recurse immediately for flat list or keep structure? 
                    # For speed, we yield paths. Structure is handled by relative path calc later.
                    files.extend(list_dir_fast(entry.path))
            except PermissionError:
                continue
        return files
    except PermissionError:
        return []

def calculate_partial_hash(filepath):
    """Calculate hash of first and last N bytes. Extremely fast."""
    hasher = hashlib.sha256()
    try:
        size = os.path.getsize(filepath)
        if size == 0:
            return hasher.hexdigest()
        
        with open(filepath, 'rb') as f:
            # Head
            head = f.read(HASH_PART_SIZE)
            hasher.update(head)
            
            # Tail (if file is larger than 2 * part size)
            if size > HASH_PART_SIZE * 2:
                f.seek(-HASH_PART_SIZE, 2)
                tail = f.read(HASH_PART_SIZE)
                hasher.update(tail)
            elif size > HASH_PART_SIZE:
                # Middle part if file is small but > part size
                f.seek(HASH_PART_SIZE)
                rest = f.read()
                hasher.update(rest)
                
        return hasher.hexdigest()
    except Exception:
        return None

def get_metadata(filepath):
    """Extract basic metadata if mutagen available, else empty dict."""
    if not HAS_MUTAGEN:
        return {}
    try:
        audio = MutagenFile(filepath)
        if audio is None:
            return {}
        meta = {}
        if hasattr(audio, 'tags') and audio.tags:
            tags = audio.tags
            # Generic extraction
            for key in ['title', 'artist', 'album', 'genre']:
                if key in tags:
                    val = tags[key]
                    if isinstance(val, list): val = val[0]
                    meta[key] = str(val)
        if hasattr(audio, 'info') and audio.info:
            meta['duration'] = getattr(audio.info, 'length', 0)
        return meta
    except Exception:
        return {}

# ==============================================================================
# CORE LOGIC
# ==============================================================================

class FileEntry:
    def __init__(self, path, base_path):
        self.abs_path = path
        self.rel_path = os.path.relpath(path, base_path)
        self.size = os.path.getsize(path)
        self.hash = None
        self.meta = {}
        self.name = os.path.basename(path)
        self.ext = os.path.splitext(path)[1].lower()

    def fingerprint(self):
        if self.hash is None:
            self.hash = calculate_partial_hash(self.abs_path)
        # Fingerprint = Hash + Size + Extension
        return f"{self.hash}:{self.size}:{self.ext}"

    def load_meta(self):
        if not self.meta:
            self.meta = get_metadata(self.abs_path)

def scan_library(base_path, lang_code):
    """Scan directory and return list of FileEntry objects."""
    raw_print(t('scanning', path=base_path))
    
    files = []
    # Use threading for IO bound scanning if deep recursion needed, 
    # but os.scandir is usually fast enough for single thread if just listing.
    # Let's use threads for the heavy lifting: hashing.
    
    raw_paths = list_dir_fast(base_path)
    count = len(raw_paths)
    raw_print(t('found_files', count=count))
    
    entries = []
    # Pre-calculate relative paths
    for p in raw_paths:
        entries.append(FileEntry(p, base_path))
    
    return entries

def process_entries(entries, label):
    """Calculate hashes and metadata in parallel."""
    raw_print(f"[{label}] Calculating fingerprints...")
    
    # Determine thread count
    workers = os.cpu_count() or 4
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_single, e): e for e in entries}
        completed = 0
        total = len(entries)
        
        for future in as_completed(futures):
            entry = future.result()
            completed += 1
            if VERBOSE:
                # Direct output, gcc style
                status = f"[{label}] {completed}/{total} : {entry.rel_path}"
                # Overwrite line or print new? GCC prints new lines for warnings/errors.
                # Let's print compact status.
                sys.stdout.write(f"\r{status:<80}")
                sys.stdout.flush()
    
    sys.stdout.write("\n") # Newline after progress
    sys.stdout.flush()
    return entries

def process_single(entry):
    entry.fingerprint()
    # Only load metadata if we might need it for decision making later
    # To save time, we skip heavy metadata loading unless requested or ambiguous
    # But for this version, let's load it to show user info
    entry.load_meta()
    return entry

def compare_libraries(source_entries, target_entries):
    """Compare two lists of FileEntry."""
    raw_print("Comparing fingerprints...")
    
    src_map = {e.fingerprint(): e for e in source_entries}
    tgt_map = {e.fingerprint(): e for e in target_entries}
    
    src_fps = set(src_map.keys())
    tgt_fps = set(tgt_map.keys())
    
    changes = []
    
    # 1. Files in Source but not in Target (New/Missing in Target)
    # These need to be COPIED to Target
    only_in_src = src_fps - tgt_fps
    for fp in only_in_src:
        src_e = src_map[fp]
        # Check if file exists in target with DIFFERENT name but same hash?
        # Our fingerprint includes extension, so if ext changed, it's a mismatch here.
        # Simple logic: Copy to same relative path
        changes.append({
            'type': 'COPY_TO_TARGET',
            'source': src_e,
            'target_rel': src_e.rel_path,
            'reason': 'Exists in Source, missing in Target'
        })
        
    # 2. Files in Target but not in Source (Extra in Target / Missing in Source)
    # These might be DELETED from Target or MOVED from Source
    only_in_tgt = tgt_fps - src_fps
    for fp in only_in_tgt:
        tgt_e = tgt_map[fp]
        # Is this a moved file? 
        # If the hash exists in Source but under a different path? 
        # Wait, our fingerprint includes path-independent data (hash+size+ext).
        # If the fingerprint matches, it means content is same.
        # But we subtracted sets of fingerprints. So these fingerprints DO NOT exist in source.
        # This means the content itself is unique to Target.
        # User decision: Delete from Target? Or Keep (Skip)?
        changes.append({
            'type': 'EXTRA_IN_TARGET',
            'target': tgt_e,
            'reason': 'Exists in Target, missing in Source'
        })

    # 3. Files in Both (Same Fingerprint) -> No action needed usually
    # Unless we want to check metadata differences? 
    # If hash is same, audio is same. Metadata diff is minor. Skip for speed.
    
    # 4. Advanced: Detect Moves/Renames where content is same but path differs?
    # Our fingerprint logic handles this IF the hash matches.
    # But wait: if I move file A to B, the fingerprint (hash+size+ext) stays SAME.
    # So it would appear in BOTH sets (intersection) and be ignored.
    # PROBLEM: We need to know if the PATH changed to update the folder structure.
    
    # REVISED STRATEGY FOR MOVES:
    # Map by Content Hash ONLY (ignore path in key)
    src_by_hash = defaultdict(list)
    for e in source_entries:
        # Use a pure content hash (size + sha)
        h = f"{e.hash}:{e.size}" 
        src_by_hash[h].append(e)
        
    tgt_by_hash = defaultdict(list)
    for e in target_entries:
        h = f"{e.hash}:{e.size}"
        tgt_by_hash[h].append(e)
        
    # Re-evaluate based on pure content
    processed_hashes = set()
    
    final_changes = []
    
    # Iterate all unique content hashes
    all_hashes = set(src_by_hash.keys()) | set(tgt_by_hash.keys())
    
    for h in all_hashes:
        src_list = src_by_hash.get(h, [])
        tgt_list = tgt_by_hash.get(h, [])
        
        src_paths = {e.rel_path for e in src_list}
        tgt_paths = {e.rel_path for e in tgt_list}
        
        # Paths in Source but not Target -> COPY
        for p in src_paths - tgt_paths:
            entry = next(e for e in src_list if e.rel_path == p)
            final_changes.append({'type': 'COPY', 'entry': entry, 'direction': 'src->tgt'})
            
        # Paths in Target but not Source -> DELETE (or confirm)
        for p in tgt_paths - src_paths:
            entry = next(e for e in tgt_list if e.rel_path == p)
            final_changes.append({'type': 'DELETE', 'entry': entry, 'direction': 'tgt-only'})
            
        # Paths in Both -> OK (No move detected because path exists in both)
        # If a file was moved from A to B:
        # Source has A. Target has B.
        # src_paths = {A}, tgt_paths = {B}
        # Result: COPY A->Tgt(A) ?? No, we want MOVE A->B.
        # This logic treats them as separate.
        # To detect MOVE: We need to match 1-to-1.
        # If count(src) == count(tgt) == 1, and paths differ -> MOVE.
        
        if len(src_list) == 1 and len(tgt_list) == 1:
            s_entry = src_list[0]
            t_entry = tgt_list[0]
            if s_entry.rel_path != t_entry.rel_path:
                # It's a move/rename!
                # Remove previous COPY/DELETE suggestions for these specific paths if added
                # Filter them out from final_changes
                final_changes = [c for c in final_changes if not (
                    (c['type'] == 'COPY' and c['entry'].rel_path == s_entry.rel_path) or
                    (c['type'] == 'DELETE' and c['entry'].rel_path == t_entry.rel_path)
                )]
                final_changes.append({'type': 'MOVE', 'source': s_entry, 'target': t_entry})

    return final_changes

def interact_with_changes(changes):
    """Interactive loop to decide actions."""
    if not changes:
        raw_print("No changes detected. Libraries are identical.")
        return []

    raw_print(t('changes_found'))
    decisions = []
    
    batch_action = None
    
    for i, change in enumerate(changes):
        ctype = change['type']
        
        # Display details
        if ctype == 'COPY':
            msg = t('new_file', path=change['entry'].rel_path)
            default = 'c'
        elif ctype == 'DELETE':
            msg = t('missing_file', path=change['entry'].rel_path)
            default = 'd' # Default to delete if missing in source? Or skip? Safe is skip.
            default = 's'
        elif ctype == 'MOVE':
            msg = t('moved_file', src=change['source'].rel_path, dst=change['target'].rel_path)
            default = 'm'
        else:
            continue
            
        raw_print(f"[{i+1}/{len(changes)}] {msg}")
        
        action = None
        while not action:
            if batch_action:
                raw_print(f"Batch mode: Applying '{batch_action}'")
                action = batch_action
            else:
                # Show options
                if ctype == 'COPY': opts = "(c)opy, (s)kip"
                elif ctype == 'DELETE': opts = "(d)elete, (s)kip"
                elif ctype == 'MOVE': opts = "(m)ove, (s)kip"
                else: opts = ""
                
                user_in = input(f"{opts} [{default}]: ").strip().lower()
                action = user_in if user_in else default
                
                if action not in ['c', 'd', 'm', 's']:
                    raw_print("Invalid option.")
                    action = None
                    continue
                
                # Batch prompt
                if not batch_action:
                    batch_in = input(t('batch_prompt', action=action)).strip().lower()
                    if batch_in == 'y':
                        batch_action = action
        
        decisions.append({'change': change, 'action': action})
        
    return decisions

def apply_decisions(decisions, src_base, tgt_base):
    """Execute the decisions."""
    if DRY_RUN:
        raw_print(t('dry_run'))
        
    for item in decisions:
        change = item['change']
        action = item['action']
        
        ctype = change['type']
        
        if action == 's':
            continue
            
        if ctype == 'COPY':
            src_path = change['entry'].abs_path
            tgt_path = os.path.join(tgt_base, change['entry'].rel_path)
            if action == 'c':
                if DRY_RUN:
                    raw_print(f"[DRY] COPY {src_path} -> {tgt_path}")
                else:
                    os.makedirs(os.path.dirname(tgt_path), exist_ok=True)
                    # Fast copy using system tools? Or python shutil?
                    # Python shutil is okay, but for huge files system cp might be faster.
                    # Sticking to python for cross-platform simplicity.
                    import shutil
                    shutil.copy2(src_path, tgt_path)
                    raw_print(f"[OK] Copied {change['entry'].rel_path}")
                    
        elif ctype == 'DELETE':
            tgt_path = change['entry'].abs_path # Already absolute in target
            if action == 'd':
                if DRY_RUN:
                    raw_print(f"[DRY] DELETE {tgt_path}")
                else:
                    os.remove(tgt_path)
                    raw_print(f"[OK] Deleted {change['entry'].rel_path}")
                    
        elif ctype == 'MOVE':
            # Move in Target: Rename target file to match source path?
            # Wait, logic: Source has A, Target has B. We want Target to have A.
            # So we rename B (in target) to A (in target).
            src_rel = change['source'].rel_path
            tgt_rel = change['target'].rel_path
            
            tgt_src_path = os.path.join(tgt_base, tgt_rel)
            tgt_dst_path = os.path.join(tgt_base, src_rel)
            
            if action == 'm':
                if DRY_RUN:
                    raw_print(f"[DRY] RENAME {tgt_rel} -> {src_rel}")
                else:
                    os.makedirs(os.path.dirname(tgt_dst_path), exist_ok=True)
                    os.rename(tgt_src_path, tgt_dst_path)
                    raw_print(f"[OK] Moved {tgt_rel} -> {src_rel}")

    # Save Log
    log_data = [{'decision': d['action'], 'change': d['change']['type']} for d in decisions]
    log_file = "gnulibrary_log.json"
    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=2, default=str)
    raw_print(t('log_saved', path=os.path.abspath(log_file)))

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    global LANG, DRY_RUN, VERBOSE
    
    # Args parsing (simple)
    args = sys.argv[1:]
    if '--dry-run' in args or '-d' in args:
        DRY_RUN = True
    if '--no-verbose' in args or '-q' in args:
        VERBOSE = False
    if '--lang' in args:
        idx = args.index('--lang')
        if idx + 1 < len(args):
            LANG = args[idx+1]

    # Welcome
    raw_print("="*60)
    raw_print(t('welcome'))
    raw_print("="*60)
    
    # Language Select
    if '--lang' not in args:
        l = input(t('select_lang')).strip().lower()
        if l in TRANSLATIONS:
            LANG = l
            
    # Path Selection
    def get_path(prompt_key):
        raw_print(t(prompt_key))
        while True:
            p = input(t('enter_path')).strip()
            if p.lower() == 'browse':
                res = get_native_picker()
                if res:
                    p = res
                else:
                    raw_print(t('error_browse'))
                    continue
            elif p.lower() == 'ls':
                raw_print("Current Dir Contents:")
                for x in os.listdir('.'): raw_print(f"  {x}")
                continue
            
            if os.path.exists(p):
                return os.path.abspath(p)
            else:
                raw_print(t('error_path'))

    src_path = get_path('select_source')
    tgt_path = get_path('select_target')
    
    raw_print(f"Source: {src_path}")
    raw_print(f"Target: {tgt_path}")
    raw_print("-" * 40)
    
    # Scan
    src_entries = scan_library(src_path, LANG)
    tgt_entries = scan_library(tgt_path, LANG)
    
    # Process (Hash)
    src_entries = process_entries(src_entries, "SRC")
    tgt_entries = process_entries(tgt_entries, "TGT")
    
    # Compare
    changes = compare_libraries(src_entries, tgt_entries)
    
    # Interact
    decisions = interact_with_changes(changes)
    
    # Confirm
    if decisions:
        confirm = input(t('confirm_apply')).strip().lower()
        if confirm in ['yes', 'y']:
            apply_decisions(decisions, src_path, tgt_path)
            raw_print(t('finish'))
        else:
            raw_print("Aborted by user.")
    else:
        raw_print(t('finish'))

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        raw_print("\nInterrupted.")
        sys.exit(1)
    except EOFError:
        raw_print("\nInput ended.")
        sys.exit(1)
