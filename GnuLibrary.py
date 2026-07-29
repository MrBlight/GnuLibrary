
"""
GnuLibrary - A smart, user-controlled file synchronization tool for music collections.
Compares two storage locations, detects changes (metadata, moves, reorganization),
and presents all decisions to the user before executing any changes.

Licensed under GNU GPL v3 (license file separate).
"""

import os
import sys
import hashlib
import json
import shutil
import argparse
import threading
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed

# Try to import mutagen, provide graceful fallback if not installed
try:
    from mutagen.mp3 import MP3
    from mutagen.oggvorbis import OggVorbis
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.id3 import ID3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("Warning: mutagen not installed. Install with: pip install mutagen")
    print("Metadata analysis will be limited to file properties only.")

# Try to import tkinter for GUI folder selection
try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    print("Warning: tkinter not available. Will use command-line path input.")

# ============================================================================
# TRANSLATION SYSTEM
# ============================================================================

TRANSLATIONS = {
    'en': {
        'welcome': "GnuLibrary - Music Collection Synchronizer",
        'select_source': "Select SOURCE storage location:",
        'select_target': "Select TARGET storage location:",
        'source_path': "Source path: {}",
        'target_path': "Target path: {}",
        'scanning': "Scanning {}...",
        'analyzing': "Analyzing files in {}...",
        'comparing': "Comparing storage locations...",
        'found_files': "Found {} files in {}",
        'found_folders': "Found {} folders in {}",
        'changes_detected': "Changes detected:",
        'new_files': "New files (exist in source, not in target):",
        'missing_files': "Missing files (exist in target, not in source):",
        'moved_files': "Moved/Renamed files:",
        'modified_files': "Modified files (metadata/content changed):",
        'folder_changes': "Folder structure changes:",
        'confirm_action': "Confirm action for '{}':",
        'copy_file': "Copy file to target",
        'delete_file': "Delete file from target",
        'move_file': "Move/rename file",
        'skip_file': "Skip this file",
        'apply_all_copy': "Apply COPY to all new files",
        'apply_all_delete': "Apply DELETE to all missing files",
        'apply_all_move': "Apply MOVE to all moved files",
        'apply_all_skip': "SKIP all remaining",
        'dry_run': "🧪 DRY RUN MODE - No changes will be made",
        'executing': "🚀 Executing changes...",
        'completed': "✅ Sync operation completed!",
        'log_saved': "Log saved to: {}",
        'error': "❌ Error: {}",
        'warning': "⚠️  Warning: {}",
        'enter_path': "Enter {} path (or 'browse' if GUI available): ",
        'invalid_path': "Invalid path. Please try again.",
        'choose_action': "Choose action (1-4): ",
        'batch_prompt': "Batch action? (y/n): ",
        'calculating_hash': "Calculating hash for {}...",
        'reading_metadata': "Reading metadata for {}...",
        'match_confidence': "Match confidence: {}%",
        'file_too_large': "File size: {} MB",
        'duration': "Duration: {} seconds",
        'metadata_diff': "Metadata differences detected",
        'content_diff': "Content differences detected",
        'proceed_with_sync': "Proceed with sync? (y/n): ",
        'cancelled': "Operation cancelled by user.",
        'language_prompt': "Select language (en/ro/ru): ",
        'new_folder': "New folders (exist in source, not in target):",
        'removed_folder': "Removed folders (exist in target, not in source):",
        'renamed_folder': "Renamed/Moved folders:",
    },
    'ro': {
        'welcome': "GnuLibrary - Sincronizare Colecție Muzicală",
        'select_source': "Selectați locația STOCARE SURSĂ:",
        'select_target': "Selectați locația STOCARE ȚINTĂ:",
        'source_path': "Cale sursă: {}",
        'target_path': "Cale țintă: {}",
        'scanning': "Se scanează {}...",
        'analyzing': "Se analizează fișierele din {}...",
        'comparing': "Se compară locațiile de stocare...",
        'found_files': "Găsite {} fișiere în {}",
        'found_folders': "Găsite {} foldere în {}",
        'changes_detected': "Modificări detectate:",
        'new_files': "Fișiere noi (există în sursă, nu în țintă):",
        'missing_files': "Fișiere lipsă (există în țintă, nu în sursă):",
        'moved_files': "Fișiere mutate/redenumite:",
        'modified_files': "Fișiere modificate (metadate/conținut schimbat):",
        'folder_changes': "Modificări structură foldere:",
        'confirm_action': "Confirmați acțiunea pentru '{}':",
        'copy_file': "Copiază fișierul în țintă",
        'delete_file': "Șterge fișierul din țintă",
        'move_file': "Mută/redenumește fișierul",
        'skip_file': "Omite acest fișier",
        'apply_all_copy': "Aplică COPIERE la toate fișierele noi",
        'apply_all_delete': "Aplică ȘTERGERE la toate fișierele lipsă",
        'apply_all_move': "Aplică MUTARE la toate fișierele mutate",
        'apply_all_skip': "OMITE toate rămase",
        'dry_run': "🧪 MOD TEST - Nu se vor face modificări",
        'executing': "🚀 Se execută modificările...",
        'completed': "✅ Operațiunea de sincronizare a fost completată!",
        'log_saved': "Jurnal salvat în: {}",
        'error': "❌ Eroare: {}",
        'warning': "⚠️  Avertisment: {}",
        'enter_path': "Introduceți calea {} (sau 'browse' dacă GUI disponibil): ",
        'invalid_path': "Cale invalidă. Încercați din nou.",
        'choose_action': "Alegeți acțiunea (1-4): ",
        'batch_prompt': "Acțiune în lot? (d/n): ",
        'calculating_hash': "Se calculează hash pentru {}...",
        'reading_metadata': "Se citesc metadatele pentru {}...",
        'match_confidence': "Încredere potrivire: {}%",
        'file_too_large': "Dimensiune fișier: {} MB",
        'duration': "Durată: {} secunde",
        'metadata_diff': "Diferențe de metadate detectate",
        'content_diff': "Diferențe de conținut detectate",
        'proceed_with_sync': "Continuați cu sincronizarea? (d/n): ",
        'cancelled': "Operațiune anulată de utilizator.",
        'language_prompt': "Selectați limba (en/ro/ru): ",
        'new_folder': "Foldere noi (există în sursă, nu în țintă):",
        'removed_folder': "Foldere eliminate (există în țintă, nu în sursă):",
        'renamed_folder': "Foldere mutate/redenumite:",
    },
    'ru': {
        'welcome': "GnuLibrary - Синхронизация Музыкальной Коллекции",
        'select_source': "Выберите расположение ИСХОДНОГО хранилища:",
        'select_target': "Выберите расположение ЦЕЛЕВОГО хранилища:",
        'source_path': "Путь источника: {}",
        'target_path': "Путь цели: {}",
        'scanning': "Сканирование {}...",
        'analyzing': "Анализ файлов в {}...",
        'comparing': "Сравнение расположений хранилищ...",
        'found_files': "Найдено {} файлов в {}",
        'found_folders': "Найдено {} папок в {}",
        'changes_detected': "Обнаружены изменения:",
        'new_files': "Новые файлы (существуют в источнике, но не в цели):",
        'missing_files': "Отсутствующие файлы (существуют в цели, но не в источнике):",
        'moved_files': "Перемещенные/переименованные файлы:",
        'modified_files': "Измененные файлы (метаданные/контент изменены):",
        'folder_changes': "Изменения структуры папок:",
        'confirm_action': "Подтвердите действие для '{}':",
        'copy_file': "Копировать файл в цель",
        'delete_file': "Удалить файл из цели",
        'move_file': "Переместить/переименовать файл",
        'skip_file': "Пропустить этот файл",
        'apply_all_copy': "Применить КОПИРОВАНИЕ ко всем новым файлам",
        'apply_all_delete': "Применить УДАЛЕНИЕ ко всем отсутствующим файлам",
        'apply_all_move': "Применить ПЕРЕМЕЩЕНИЕ ко всем перемещенным файлам",
        'apply_all_skip': "ПРОПУСТИТЬ все остальные",
        'dry_run': "🧪 РЕЖИМ ТЕСТА - Изменения не будут внесены",
        'executing': "🚀 Выполнение изменений...",
        'completed': "✅ Операция синхронизации завершена!",
        'log_saved': "Журнал сохранен в: {}",
        'error': "❌ Ошибка: {}",
        'warning': "⚠️  Предупреждение: {}",
        'enter_path': "Введите путь {} (или 'browse' если GUI доступен): ",
        'invalid_path': "Неверный путь. Попробуйте снова.",
        'choose_action': "Выберите действие (1-4): ",
        'batch_prompt': "Пакетное действие? (д/н): ",
        'calculating_hash': "Вычисление хэша для {}...",
        'reading_metadata': "Чтение метаданных для {}...",
        'match_confidence': "Уверенность совпадения: {}%",
        'file_too_large': "Размер файла: {} МБ",
        'duration': "Продолжительность: {} секунд",
        'metadata_diff': "Обнаружены различия в метаданных",
        'content_diff': "Обнаружены различия в контенте",
        'proceed_with_sync': "Продолжить синхронизацию? (д/н): ",
        'cancelled': "Операция отменена пользователем.",
        'language_prompt': "Выберите язык (en/ro/ru): ",
        'new_folder': "Новые папки (существуют в источнике, но не в цели):",
        'removed_folder': "Удаленные папки (существуют в цели, но не в источнике):",
        'renamed_folder': "Переименованные/перемещенные папки:",
    }
}

def get_translation(lang_code, key, *args):
    """Get translated string with optional formatting arguments."""
    if lang_code not in TRANSLATIONS:
        lang_code = 'en'

    text = TRANSLATIONS[lang_code].get(key, TRANSLATIONS['en'].get(key, key))
    if args:
        return text.format(*args)
    return text

def add_translation(lang_code, translations_dict):
    """Add or update translations for a language."""
    if lang_code not in TRANSLATIONS:
        TRANSLATIONS[lang_code] = {}
    TRANSLATIONS[lang_code].update(translations_dict)

# ============================================================================
# FILE FINGERPRINTING AND METADATA ANALYSIS
# ============================================================================

class FileFingerprint:
    """Represents a comprehensive fingerprint of a file for comparison."""

    def __init__(self, filepath, base_path):
        self.filepath = Path(filepath)
        self.base_path = Path(base_path)
        self.relative_path = self.filepath.relative_to(self.base_path)
        self.size = 0
        self.mtime = 0
        self.hash_partial = None
        self.hash_full = None
        self.duration = None
        self.metadata = {}
        self.file_type = None
        self.error = None

        self._analyze()

    def _analyze(self):
        """Perform comprehensive file analysis."""
        try:
            if not self.filepath.exists():
                self.error = "File does not exist"
                return

            # Basic file properties
            stat_info = self.filepath.stat()
            self.size = stat_info.st_size
            self.mtime = stat_info.st_mtime

            # Determine file type
            ext = self.filepath.suffix.lower()
            self.file_type = ext

            # Calculate partial hash (first 1MB + last 1MB for large files)
            self._calculate_partial_hash()

            # Extract metadata for audio files
            if MUTAGEN_AVAILABLE and ext in ['.mp3', '.ogg', '.oga', '.flac', '.m4a', '.mp4']:
                self._extract_metadata()

        except Exception as e:
            self.error = str(e)

    def _calculate_partial_hash(self):
        """Calculate hash of file parts for quick comparison."""
        try:
            hasher = hashlib.md5()
            file_size = self.size

            with open(self.filepath, 'rb') as f:
                # Read first 1MB
                chunk = f.read(1024 * 1024)
                hasher.update(chunk)

                # For files larger than 2MB, also read last 1MB
                if file_size > 2 * 1024 * 1024:
                    f.seek(-1024 * 1024, 2)  # Seek from end
                    chunk = f.read(1024 * 1024)
                    hasher.update(chunk)

            self.hash_partial = hasher.hexdigest()

        except Exception as e:
            self.hash_partial = None

    def _extract_metadata(self):
        """Extract audio metadata using mutagen."""
        try:
            ext = self.file_type
            audio = None

            if ext == '.mp3':
                audio = MP3(str(self.filepath))
                if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                    self.duration = audio.info.length
            elif ext in ['.ogg', '.oga']:
                audio = OggVorbis(str(self.filepath))
                if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                    self.duration = audio.info.length
            elif ext == '.flac':
                audio = FLAC(str(self.filepath))
                if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                    self.duration = audio.info.length
            elif ext in ['.m4a', '.mp4']:
                audio = MP4(str(self.filepath))
                if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                    self.duration = audio.info.length

            # Extract common tags
            if audio and hasattr(audio, 'tags') and audio.tags:
                tags = audio.tags
                self.metadata = {
                    'title': str(tags.get('title', [''])[0]) if tags.get('title') else '',
                    'artist': str(tags.get('artist', [''])[0]) if tags.get('artist') else '',
                    'album': str(tags.get('album', [''])[0]) if tags.get('album') else '',
                    'genre': str(tags.get('genre', [''])[0]) if tags.get('genre') else '',
                    'year': str(tags.get('date', [''])[0]) if tags.get('date') else '',
                    'track': str(tags.get('tracknumber', [''])[0]) if tags.get('tracknumber') else '',
                }

        except Exception as e:
            self.metadata = {'error': str(e)}

    def calculate_full_hash(self):
        """Calculate full file hash (expensive operation)."""
        if self.hash_full:
            return self.hash_full

        try:
            hasher = hashlib.sha256()
            with open(self.filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            self.hash_full = hasher.hexdigest()
            return self.hash_full
        except Exception:
            return None

    def matches(self, other, threshold=0.8):
        """
        Determine if this file matches another file with given confidence.
        Returns tuple: (is_match, confidence_score, reason)
        """
        if self.error or other.error:
            return False, 0.0, "Error in file analysis"

        # Exact same relative path and hash
        if self.relative_path == other.relative_path and self.hash_partial == other.hash_partial:
            return True, 1.0, "Exact match (path + hash)"

        # Same size and partial hash
        if self.size == other.size and self.hash_partial == other.hash_partial:
            return True, 0.95, "Same size and partial hash"

        # Similar size and duration (for audio files)
        if self.file_type in ['.mp3', '.ogg', '.oga', '.flac', '.m4a', '.mp4'] and \
           other.file_type in ['.mp3', '.ogg', '.oga', '.flac', '.m4a', '.mp4']:

            size_diff = abs(self.size - other.size) / max(self.size, other.size, 1)
            duration_diff = 0
            if self.duration and other.duration:
                duration_diff = abs(self.duration - other.duration) / max(self.duration, other.duration, 1)

            if size_diff < 0.05 and duration_diff < 0.05:  # Within 5%
                # Check metadata similarity
                metadata_score = self._compare_metadata(other)
                confidence = 1.0 - max(size_diff, duration_diff) * 0.5 + metadata_score * 0.3
                confidence = min(confidence, 0.99)

                if confidence >= threshold:
                    return True, confidence, f"Audio match (size/duration/metadata: {confidence:.0%})"

        # Filename similarity (for potential renames)
        name_similarity = SequenceMatcher(None,
                                         self.filepath.name,
                                         other.filepath.name).ratio()

        if name_similarity > 0.7 and self.size == other.size:
            return True, 0.75, f"Name similarity ({name_similarity:.0%}) + same size"

        return False, 0.0, "No significant match"

    def _compare_metadata(self, other):
        """Compare metadata between two files, return similarity score 0-1."""
        if not self.metadata or not other.metadata:
            return 0.0

        matching_fields = 0
        total_fields = 0

        for field in ['title', 'artist', 'album', 'genre']:
            val1 = self.metadata.get(field, '').lower().strip()
            val2 = other.metadata.get(field, '').lower().strip()

            if val1 or val2:  # At least one has value
                total_fields += 1
                if val1 == val2:
                    matching_fields += 1
                elif val1 and val2:
                    # Partial match
                    similarity = SequenceMatcher(None, val1, val2).ratio()
                    if similarity > 0.8:
                        matching_fields += similarity

        return matching_fields / total_fields if total_fields > 0 else 0.0

    def to_dict(self):
        """Convert fingerprint to dictionary for logging."""
        return {
            'relative_path': str(self.relative_path),
            'size': self.size,
            'mtime': self.mtime,
            'hash_partial': self.hash_partial,
            'duration': self.duration,
            'metadata': self.metadata,
            'file_type': self.file_type,
            'error': self.error
        }

# ============================================================================
# STORAGE SCANNER
# ============================================================================

class StorageScanner:
    """Scans a storage location and builds a database of file fingerprints."""

    def __init__(self, base_path, lang='en', verbose=True):
        self.base_path = Path(base_path).resolve()
        self.lang = lang
        self.verbose = verbose
        self.files = {}  # relative_path -> FileFingerprint
        self.folders = set()
        self.errors = []

    def scan(self, progress_callback=None):
        """Scan the entire storage location."""
        if not self.base_path.exists():
            raise ValueError(f"Path does not exist: {self.base_path}")

        if self.verbose:
            print(get_translation(self.lang, 'scanning', str(self.base_path)))

        file_count = 0
        folder_count = 0

        # Use ThreadPoolExecutor for parallel scanning
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []

            for root, dirs, files in os.walk(self.base_path):
                # Track folders
                root_path = Path(root)
                rel_root = root_path.relative_to(self.base_path)

                if rel_root != Path('.'):
                    self.folders.add(str(rel_root))
                    folder_count += 1

                # Submit file analysis tasks
                for filename in files:
                    filepath = root_path / filename
                    future = executor.submit(self._analyze_file, filepath)
                    futures.append(future)
                    file_count += 1

                    if progress_callback and file_count % 100 == 0:
                        progress_callback(file_count, "files")

            # Collect results
            for i, future in enumerate(as_completed(futures)):
                try:
                    fingerprint = future.result()
                    if fingerprint and not fingerprint.error:
                        self.files[fingerprint.relative_path] = fingerprint
                    elif fingerprint and fingerprint.error:
                        self.errors.append((str(fingerprint.filepath), fingerprint.error))
                except Exception as e:
                    self.errors.append(("Unknown", str(e)))

                if progress_callback and (i + 1) % 100 == 0:
                    progress_callback(i + 1, f"of {len(futures)} analyzed")

        if self.verbose:
            print(get_translation(self.lang, 'found_files', len(self.files), str(self.base_path)))
            print(get_translation(self.lang, 'found_folders', len(self.folders), str(self.base_path)))

        return len(self.files), len(self.folders)

    def _analyze_file(self, filepath):
        """Analyze a single file (called in thread)."""
        try:
            return FileFingerprint(filepath, self.base_path)
        except Exception as e:
            fp = FileFingerprint.__new__(FileFingerprint)
            fp.filepath = filepath
            fp.base_path = self.base_path
            fp.relative_path = filepath.relative_to(self.base_path)
            fp.error = str(e)
            return fp

# ============================================================================
# COMPARISON ENGINE
# ============================================================================

class ChangeType:
    NEW_FILE = "new_file"
    MISSING_FILE = "missing_file"
    MOVED_FILE = "moved_file"
    MODIFIED_FILE = "modified_file"
    NEW_FOLDER = "new_folder"
    REMOVED_FOLDER = "removed_folder"
    MOVED_FOLDER = "moved_folder"

class SyncChange:
    """Represents a single change detected between two storages."""

    def __init__(self, change_type, source_item=None, target_item=None,
                 confidence=1.0, reason="", metadata_diff=None):
        self.change_type = change_type
        self.source_item = source_item  # FileFingerprint or folder path
        self.target_item = target_item  # FileFingerprint or folder path
        self.confidence = confidence
        self.reason = reason
        self.metadata_diff = metadata_diff or {}
        self.user_action = None  # Will be set by user interaction
        self.applied = False

    def __str__(self):
        if self.change_type == ChangeType.NEW_FILE:
            return f"NEW: {self.source_item.relative_path}"
        elif self.change_type == ChangeType.MISSING_FILE:
            return f"MISSING: {self.target_item.relative_path}"
        elif self.change_type == ChangeType.MOVED_FILE:
            return f"MOVED: {self.target_item.relative_path} → {self.source_item.relative_path}"
        elif self.change_type == ChangeType.MODIFIED_FILE:
            return f"MODIFIED: {self.source_item.relative_path}"
        elif self.change_type == ChangeType.NEW_FOLDER:
            return f"NEW FOLDER: {self.source_item}"
        elif self.change_type == ChangeType.REMOVED_FOLDER:
            return f"REMOVED FOLDER: {self.target_item}"
        elif self.change_type == ChangeType.MOVED_FOLDER:
            return f"MOVED FOLDER: {self.target_item} → {self.source_item}"
        return f"UNKNOWN: {self.change_type}"

class ComparisonEngine:
    """Compares two storage scanners and identifies all changes."""

    def __init__(self, source_scanner, target_scanner, lang='en', verbose=True):
        self.source = source_scanner
        self.target = target_scanner
        self.lang = lang
        self.verbose = verbose
        self.changes = []

    def compare(self, progress_callback=None):
        """Perform comprehensive comparison."""
        if self.verbose:
            print(get_translation(self.lang, 'comparing'))

        # Track processed items to avoid duplicates
        processed_source = set()
        processed_target = set()

        source_files = dict(self.source.files)
        target_files = dict(self.target.files)

        total_comparisons = len(source_files) + len(target_files)
        current = 0

        # Step 1: Find exact and near matches
        for src_path, src_fp in source_files.items():
            if src_path in target_files:
                # Same relative path exists
                tgt_fp = target_files[src_path]
                processed_source.add(src_path)
                processed_target.add(src_path)

                # Check if modified
                is_same, confidence, reason = src_fp.matches(tgt_fp)
                if not is_same:
                    # Analyze what changed
                    metadata_diff = self._compare_metadata(src_fp, tgt_fp)
                    content_changed = src_fp.hash_partial != tgt_fp.hash_partial

                    change = SyncChange(
                        ChangeType.MODIFIED_FILE,
                        source_item=src_fp,
                        target_item=tgt_fp,
                        confidence=confidence,
                        reason=reason,
                        metadata_diff=metadata_diff
                    )
                    self.changes.append(change)
            else:
                # Look for moved/renamed file
                best_match = None
                best_confidence = 0
                best_reason = ""

                for tgt_path, tgt_fp in target_files.items():
                    if tgt_path in processed_target:
                        continue

                    is_match, confidence, reason = src_fp.matches(tgt_fp)
                    if is_match and confidence > best_confidence:
                        best_match = tgt_fp
                        best_confidence = confidence
                        best_reason = reason

                if best_match and best_confidence > 0.7:
                    # Found a move/rename
                    processed_source.add(src_path)
                    processed_target.add(best_match.relative_path)

                    change = SyncChange(
                        ChangeType.MOVED_FILE,
                        source_item=src_fp,
                        target_item=best_match,
                        confidence=best_confidence,
                        reason=best_reason
                    )
                    self.changes.append(change)
                else:
                    # New file in source
                    processed_source.add(src_path)
                    change = SyncChange(
                        ChangeType.NEW_FILE,
                        source_item=src_fp,
                        confidence=1.0,
                        reason="Exists in source only"
                    )
                    self.changes.append(change)

            current += 1
            if progress_callback and current % 100 == 0:
                progress_callback(current, total_comparisons)

        # Step 2: Find missing files (in target but not matched in source)
        for tgt_path, tgt_fp in target_files.items():
            if tgt_path not in processed_target:
                processed_target.add(tgt_path)
                change = SyncChange(
                    ChangeType.MISSING_FILE,
                    target_item=tgt_fp,
                    confidence=1.0,
                    reason="Exists in target only"
                )
                self.changes.append(change)

        # Step 3: Compare folder structures
        self._compare_folders()

        # Sort changes by type for better presentation
        type_order = [
            ChangeType.NEW_FOLDER,
            ChangeType.REMOVED_FOLDER,
            ChangeType.MOVED_FOLDER,
            ChangeType.NEW_FILE,
            ChangeType.MISSING_FILE,
            ChangeType.MOVED_FILE,
            ChangeType.MODIFIED_FILE,
        ]

        self.changes.sort(key=lambda c: (type_order.index(c.change_type) if c.change_type in type_order else 99, str(c)))

        if self.verbose:
            print(get_translation(self.lang, 'changes_detected'))
            for change in self.changes[:10]:  # Show first 10
                print(f"  {change}")
            if len(self.changes) > 10:
                print(f"  ... and {len(self.changes) - 10} more changes")

        return self.changes

    def _compare_metadata(self, src_fp, tgt_fp):
        """Compare metadata between two files, return differences dict."""
        diff = {}

        for field in ['title', 'artist', 'album', 'genre', 'year', 'track']:
            src_val = src_fp.metadata.get(field, '')
            tgt_val = tgt_fp.metadata.get(field, '')

            if src_val != tgt_val:
                diff[field] = {'source': src_val, 'target': tgt_val}

        if src_fp.duration and tgt_fp.duration:
            if abs(src_fp.duration - tgt_fp.duration) > 0.1:
                diff['duration'] = {'source': src_fp.duration, 'target': tgt_fp.duration}

        return diff

    def _compare_folders(self):
        """Compare folder structures."""
        source_folders = self.source.folders
        target_folders = self.target.folders

        # New folders in source
        for folder in source_folders:
            if folder not in target_folders:
                self.changes.append(SyncChange(
                    ChangeType.NEW_FOLDER,
                    source_item=folder,
                    confidence=1.0,
                    reason="Folder exists in source only"
                ))

        # Removed folders (in target but not source)
        for folder in target_folders:
            if folder not in source_folders:
                self.changes.append(SyncChange(
                    ChangeType.REMOVED_FOLDER,
                    target_item=folder,
                    confidence=1.0,
                    reason="Folder exists in target only"
                ))

# ============================================================================
# USER INTERACTION MANAGER
# ============================================================================

class InteractionManager:
    """Handles all user interactions for decision making."""

    def __init__(self, lang='en'):
        self.lang = lang
        self.batch_actions = {}

    def select_folder_gui(self, title):
        """Open GUI folder selector if tkinter available."""
        if not TKINTER_AVAILABLE:
            return None

        root = tk.Tk()
        root.withdraw()  # Hide main window
        root.attributes('-topmost', True)  # Bring to front

        folder_path = filedialog.askdirectory(title=title)
        root.destroy()

        return folder_path if folder_path else None

    def get_path_input(self, prompt_key):
        """Get path from user via CLI or GUI."""
        while True:
            if TKINTER_AVAILABLE:
                user_input = input(get_translation(self.lang, 'enter_path', prompt_key)).strip()
                if user_input.lower() == 'browse':
                    path = self.select_folder_gui(get_translation(self.lang, 'select_' + prompt_key))
                    if path:
                        return path
                elif user_input:
                    if os.path.isdir(user_input):
                        return os.path.abspath(user_input)
                    else:
                        print(get_translation(self.lang, 'invalid_path'))
            else:
                path = input(get_translation(self.lang, 'enter_path', prompt_key)).strip()
                if os.path.isdir(path):
                    return os.path.abspath(path)
                else:
                    print(get_translation(self.lang, 'invalid_path'))

    def present_change(self, change, index, total):
        """Present a single change to user and get decision."""
        print("\n" + "=" * 60)
        print(f"[{index}/{total}] {change.change_type.upper()}")
        print("=" * 60)

        if change.change_type in [ChangeType.NEW_FILE, ChangeType.MODIFIED_FILE]:
            item = change.source_item
            print(f"File: {item.relative_path}")
            print(f"Size: {item.size / 1024 / 1024:.2f} MB")
            if item.duration:
                print(f"Duration: {item.duration:.1f}s")
            if item.metadata.get('title'):
                print(f"Title: {item.metadata['title']}")
            if item.metadata.get('artist'):
                print(f"Artist: {item.metadata['artist']}")

            print("\nActions:")
            print("1. " + get_translation(self.lang, 'copy_file'))
            if change.change_type == ChangeType.MODIFIED_FILE:
                print("2. Keep target version (skip)")
            else:
                print("2. " + get_translation(self.lang, 'skip_file'))
            print("3. " + get_translation(self.lang, 'apply_all_copy'))
            print("4. " + get_translation(self.lang, 'apply_all_skip'))

            while True:
                choice = input(get_translation(self.lang, 'choose_action')).strip()
                if choice == '1':
                    change.user_action = 'copy'
                    break
                elif choice == '2':
                    change.user_action = 'skip'
                    break
                elif choice == '3':
                    self.batch_actions['new'] = 'copy'
                    change.user_action = 'copy'
                    break
                elif choice == '4':
                    self.batch_actions['new'] = 'skip'
                    change.user_action = 'skip'
                    break

        elif change.change_type == ChangeType.MISSING_FILE:
            item = change.target_item
            print(f"File: {item.relative_path}")
            print(f"Size: {item.size / 1024 / 1024:.2f} MB")

            print("\nActions:")
            print("1. " + get_translation(self.lang, 'delete_file'))
            print("2. " + get_translation(self.lang, 'skip_file'))
            print("3. " + get_translation(self.lang, 'apply_all_delete'))
            print("4. " + get_translation(self.lang, 'apply_all_skip'))

            while True:
                choice = input(get_translation(self.lang, 'choose_action')).strip()
                if choice == '1':
                    change.user_action = 'delete'
                    break
                elif choice == '2':
                    change.user_action = 'skip'
                    break
                elif choice == '3':
                    self.batch_actions['missing'] = 'delete'
                    change.user_action = 'delete'
                    break
                elif choice == '4':
                    self.batch_actions['missing'] = 'skip'
                    change.user_action = 'skip'
                    break

        elif change.change_type == ChangeType.MOVED_FILE:
            print(f"From: {change.target_item.relative_path}")
            print(f"To: {change.source_item.relative_path}")
            print(f"Confidence: {change.confidence:.0%}")
            print(f"Reason: {change.reason}")

            print("\nActions:")
            print("1. " + get_translation(self.lang, 'move_file'))
            print("2. " + get_translation(self.lang, 'skip_file'))
            print("3. " + get_translation(self.lang, 'apply_all_move'))
            print("4. " + get_translation(self.lang, 'apply_all_skip'))

            while True:
                choice = input(get_translation(self.lang, 'choose_action')).strip()
                if choice == '1':
                    change.user_action = 'move'
                    break
                elif choice == '2':
                    change.user_action = 'skip'
                    break
                elif choice == '3':
                    self.batch_actions['moved'] = 'move'
                    change.user_action = 'move'
                    break
                elif choice == '4':
                    self.batch_actions['moved'] = 'skip'
                    change.user_action = 'skip'
                    break

        elif change.change_type in [ChangeType.NEW_FOLDER, ChangeType.REMOVED_FOLDER, ChangeType.MOVED_FOLDER]:
            if change.change_type == ChangeType.NEW_FOLDER:
                print(f"New folder: {change.source_item}")
                action_desc = "Create folder"
            elif change.change_type == ChangeType.REMOVED_FOLDER:
                print(f"Removed folder: {change.target_item}")
                action_desc = "Remove folder"
            else:
                print(f"From: {change.target_item}")
                print(f"To: {change.source_item}")
                action_desc = "Move folder"

            print("\nActions:")
            print(f"1. {action_desc}")
            print("2. Skip")

            while True:
                choice = input(get_translation(self.lang, 'choose_action')).strip()
                if choice == '1':
                    change.user_action = 'apply'
                    break
                elif choice == '2':
                    change.user_action = 'skip'
                    break

        return change.user_action

    def apply_batch_action(self, change):
        """Apply batch action if available."""
        batch_map = {
            ChangeType.NEW_FILE: self.batch_actions.get('new'),
            ChangeType.MISSING_FILE: self.batch_actions.get('missing'),
            ChangeType.MOVED_FILE: self.batch_actions.get('moved'),
        }

        batch_action = batch_map.get(change.change_type)
        if batch_action:
            change.user_action = batch_action
            return True
        return False

    def confirm_sync(self, changes):
        """Ask user to confirm proceeding with sync."""
        pending = sum(1 for c in changes if c.user_action and c.user_action != 'skip')

        if pending == 0:
            print("\nNo actions selected. Nothing to do.")
            return False

        print(f"\n{pending} changes will be applied.")
        response = input(get_translation(self.lang, 'proceed_with_sync')).strip().lower()
        return response in ['y', 'yes', 'д', 'да']

# ============================================================================
# SYNC EXECUTOR
# ============================================================================

class SyncExecutor:
    """Executes the approved sync changes."""

    def __init__(self, source_path, target_path, lang='en', dry_run=False, verbose=True):
        self.source_path = Path(source_path)
        self.target_path = Path(target_path)
        self.lang = lang
        self.dry_run = dry_run
        self.verbose = verbose
        self.log_entries = []

    def execute(self, changes):
        """Execute all approved changes."""
        if self.dry_run:
            print("\n" + get_translation(self.lang, 'dry_run'))

        if self.verbose:
            print(get_translation(self.lang, 'executing'))

        success_count = 0
        error_count = 0

        for i, change in enumerate(changes, 1):
            if not change.user_action or change.user_action == 'skip':
                continue

            try:
                if self.dry_run:
                    print(f"[DRY RUN] Would {change.user_action}: {change}")
                    success_count += 1
                else:
                    self._execute_change(change)
                    change.applied = True
                    success_count += 1
                    self._log_change(change, "SUCCESS")
            except Exception as e:
                error_count += 1
                self._log_change(change, f"ERROR: {e}")
                print(get_translation(self.lang, 'error', str(e)))

        if self.verbose:
            print(f"\nCompleted: {success_count} successful, {error_count} errors")

        return success_count, error_count

    def _execute_change(self, change):
        """Execute a single change."""
        if change.change_type == ChangeType.NEW_FILE:
            src_file = self.source_path / change.source_item.relative_path
            tgt_file = self.target_path / change.source_item.relative_path

            # Create parent directories
            tgt_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(str(src_file), str(tgt_file))

        elif change.change_type == ChangeType.MISSING_FILE:
            tgt_file = self.target_path / change.target_item.relative_path

            if tgt_file.exists():
                tgt_file.unlink()

        elif change.change_type == ChangeType.MOVED_FILE:
            old_file = self.target_path / change.target_item.relative_path
            new_file = self.target_path / change.source_item.relative_path

            # Create parent directories
            new_file.parent.mkdir(parents=True, exist_ok=True)

            if old_file.exists():
                shutil.move(str(old_file), str(new_file))
            else:
                # Source doesn't exist, copy from source storage
                src_file = self.source_path / change.source_item.relative_path
                if src_file.exists():
                    shutil.copy2(str(src_file), str(new_file))

        elif change.change_type == ChangeType.MODIFIED_FILE:
            src_file = self.source_path / change.source_item.relative_path
            tgt_file = self.target_path / change.source_item.relative_path

            if change.user_action == 'copy':
                shutil.copy2(str(src_file), str(tgt_file))

        elif change.change_type == ChangeType.NEW_FOLDER:
            folder_path = self.target_path / change.source_item
            folder_path.mkdir(parents=True, exist_ok=True)

        elif change.change_type == ChangeType.REMOVED_FOLDER:
            folder_path = self.target_path / change.target_item
            if folder_path.exists():
                shutil.rmtree(str(folder_path))

        elif change.change_type == ChangeType.MOVED_FOLDER:
            old_path = self.target_path / change.target_item
            new_path = self.target_path / change.source_item

            if old_path.exists():
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_path), str(new_path))

    def _log_change(self, change, status):
        """Log a change execution."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'change_type': change.change_type,
            'description': str(change),
            'action': change.user_action,
            'status': status,
        }
        self.log_entries.append(entry)

    def save_log(self, target_path=None):
        """Save execution log to file."""
        if not target_path:
            target_path = self.target_path

        log_file = Path(target_path) / f"sync_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        log_data = {
            'sync_time': datetime.now().isoformat(),
            'source': str(self.source_path),
            'target': str(self.target_path),
            'dry_run': self.dry_run,
            'changes': self.log_entries,
        }

        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        return str(log_file)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class MusicSyncApp:
    """Main application orchestrator."""

    def __init__(self):
        self.lang = 'en'
        self.dry_run = False
        self.verbose = True
        self.source_path = None
        self.target_path = None
        self.interaction = None

    def select_language(self):
        """Let user select language."""
        print("\nAvailable languages: en (English), ro (Română), ru (Русский)")
        while True:
            lang = input(get_translation('en', 'language_prompt')).strip().lower()
            if lang in ['en', 'english']:
                self.lang = 'en'
                break
            elif lang in ['ro', 'romana', 'română']:
                self.lang = 'ro'
                break
            elif lang in ['ru', 'russian', 'русский']:
                self.lang = 'ru'
                break
            else:
                print("Invalid choice, defaulting to English.")
                self.lang = 'en'
                break

    def run(self):
        """Run the main application loop."""
        # Initialize interaction manager early
        self.interaction = InteractionManager(self.lang)

        print("\n" + "=" * 60)
        print(get_translation(self.lang, 'welcome'))
        print("=" * 60)

        # Language selection
        self.select_language()

        # Update interaction manager with selected language
        self.interaction.lang = self.lang

        # Get paths
        print("\n" + get_translation(self.lang, 'select_source'))
        self.source_path = self.interaction.get_path_input('source')

        print("\n" + get_translation(self.lang, 'select_target'))
        self.target_path = self.interaction.get_path_input('target')

        print(get_translation(self.lang, 'source_path', self.source_path))
        print(get_translation(self.lang, 'target_path', self.target_path))

        # Scan source
        print("\n")
        source_scanner = StorageScanner(self.source_path, self.lang, self.verbose)
        source_scanner.scan()

        # Scan target
        print("\n")
        target_scanner = StorageScanner(self.target_path, self.lang, self.verbose)
        target_scanner.scan()

        # Compare
        print("\n")
        engine = ComparisonEngine(source_scanner, target_scanner, self.lang, self.verbose)
        changes = engine.compare()

        if not changes:
            print("\n✅ No changes detected. Storages are in sync!")
            return

        # Interactive review
        print("\n" + "=" * 60)
        print("REVIEW CHANGES")
        print("=" * 60)

        self.interaction = InteractionManager(self.lang)

        for i, change in enumerate(changes, 1):
            # Check for batch action first
            if not self.interaction.apply_batch_action(change):
                self.interaction.present_change(change, i, len(changes))

        # Confirm
        if not self.interaction.confirm_sync(changes):
            print(get_translation(self.lang, 'cancelled'))
            return

        # Execute
        executor = SyncExecutor(
            self.source_path,
            self.target_path,
            self.lang,
            self.dry_run,
            self.verbose
        )

        success, errors = executor.execute(changes)

        # Save log
        if not self.dry_run:
            log_path = executor.save_log()
            print(get_translation(self.lang, 'log_saved', log_path))

        print("\n" + get_translation(self.lang, 'completed'))

def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description='GnuLibrary - Smart file synchronization for music collections'
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Perform a test run without making changes')
    parser.add_argument('--no-verbose', action='store_true',
                       help='Reduce output verbosity')
    parser.add_argument('--lang', choices=['en', 'ro', 'ru'], default='en',
                       help='Language preference')

    args = parser.parse_args()

    app = MusicSyncApp()
    app.dry_run = args.dry_run
    app.verbose = not args.no_verbose
    app.lang = args.lang

    try:
        app.run()
    except KeyboardInterrupt:
        print("\n\nOperation interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

+++ GnuLibrary.py (修改后)
#!/usr/bin/env python3
"""
GnuLibrary - A smart, user-controlled file synchronization tool for music collections.
Compares two storage locations, detects changes (metadata, moves, reorganization),
and presents all decisions to the user before executing any changes.

Licensed under GNU GPL v3 (license file separate).
"""

import os
import sys
import hashlib
import json
import shutil
import argparse
import threading
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed

# Try to import mutagen, provide graceful fallback if not installed
try:
    from mutagen.mp3 import MP3
    from mutagen.oggvorbis import OggVorbis
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.id3 import ID3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("Warning: mutagen not installed. Install with: pip install mutagen")
    print("Metadata analysis will be limited to file properties only.")

# Try to import tkinter for GUI folder selection
try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    print("Warning: tkinter not available. Will use command-line path input.")

# ============================================================================
# TRANSLATION SYSTEM
# ============================================================================

TRANSLATIONS = {
    'en': {
        'welcome': "GnuLibrary - Music Collection Synchronizer",
        'select_source': "Select SOURCE storage location:",
        'select_target': "Select TARGET storage location:",
        'source_path': "Source path: {}",
        'target_path': "Target path: {}",
        'scanning': "Scanning {}...",
        'analyzing': "Analyzing files in {}...",
        'comparing': "Comparing storage locations...",
        'found_files': "Found {} files in {}",
        'found_folders': "Found {} folders in {}",
        'changes_detected': "Changes detected:",
        'new_files': "New files (exist in source, not in target):",
        'missing_files': "Missing files (exist in target, not in source):",
        'moved_files': "Moved/Renamed files:",
        'modified_files': "Modified files (metadata/content changed):",
        'folder_changes': "Folder structure changes:",
        'confirm_action': "Confirm action for '{}':",
        'copy_file': "Copy file to target",
        'delete_file': "Delete file from target",
        'move_file': "Move/rename file",
        'skip_file': "Skip this file",
        'apply_all_copy': "Apply COPY to all new files",
        'apply_all_delete': "Apply DELETE to all missing files",
        'apply_all_move': "Apply MOVE to all moved files",
        'apply_all_skip': "SKIP all remaining",
        'dry_run': "🧪 DRY RUN MODE - No changes will be made",
        'executing': "🚀 Executing changes...",
        'completed': "✅ Sync operation completed!",
        'log_saved': "Log saved to: {}",
        'error': "❌ Error: {}",
        'warning': "⚠️  Warning: {}",
        'enter_path': "Enter {} path (or 'browse' if GUI available): ",
        'invalid_path': "Invalid path. Please try again.",
        'choose_action': "Choose action (1-4): ",
        'batch_prompt': "Batch action? (y/n): ",
        'calculating_hash': "Calculating hash for {}...",
        'reading_metadata': "Reading metadata for {}...",
        'match_confidence': "Match confidence: {}%",
        'file_too_large': "File size: {} MB",
        'duration': "Duration: {} seconds",
        'metadata_diff': "Metadata differences detected",
        'content_diff': "Content differences detected",
        'proceed_with_sync': "Proceed with sync? (y/n): ",
        'cancelled': "Operation cancelled by user.",
        'language_prompt': "Select language (en/ro/ru): ",
        'new_folder': "New folders (exist in source, not in target):",
        'removed_folder': "Removed folders (exist in target, not in source):",
        'renamed_folder': "Renamed/Moved folders:",
    },
    'ro': {
        'welcome': "GnuLibrary - Sincronizare Colecție Muzicală",
        'select_source': "Selectați locația STOCARE SURSĂ:",
        'select_target': "Selectați locația STOCARE ȚINTĂ:",
        'source_path': "Cale sursă: {}",
        'target_path': "Cale țintă: {}",
        'scanning': "Se scanează {}...",
        'analyzing': "Se analizează fișierele din {}...",
        'comparing': "Se compară locațiile de stocare...",
        'found_files': "Găsite {} fișiere în {}",
        'found_folders': "Găsite {} foldere în {}",
        'changes_detected': "Modificări detectate:",
        'new_files': "Fișiere noi (există în sursă, nu în țintă):",
        'missing_files': "Fișiere lipsă (există în țintă, nu în sursă):",
        'moved_files': "Fișiere mutate/redenumite:",
        'modified_files': "Fișiere modificate (metadate/conținut schimbat):",
        'folder_changes': "Modificări structură foldere:",
        'confirm_action': "Confirmați acțiunea pentru '{}':",
        'copy_file': "Copiază fișierul în țintă",
        'delete_file': "Șterge fișierul din țintă",
        'move_file': "Mută/redenumește fișierul",
        'skip_file': "Omite acest fișier",
        'apply_all_copy': "Aplică COPIERE la toate fișierele noi",
        'apply_all_delete': "Aplică ȘTERGERE la toate fișierele lipsă",
        'apply_all_move': "Aplică MUTARE la toate fișierele mutate",
        'apply_all_skip': "OMITE toate rămase",
        'dry_run': "🧪 MOD TEST - Nu se vor face modificări",
        'executing': "🚀 Se execută modificările...",
        'completed': "✅ Operațiunea de sincronizare a fost completată!",
        'log_saved': "Jurnal salvat în: {}",
        'error': "❌ Eroare: {}",
        'warning': "⚠️  Avertisment: {}",
        'enter_path': "Introduceți calea {} (sau 'browse' dacă GUI disponibil): ",
        'invalid_path': "Cale invalidă. Încercați din nou.",
        'choose_action': "Alegeți acțiunea (1-4): ",
        'batch_prompt': "Acțiune în lot? (d/n): ",
        'calculating_hash': "Se calculează hash pentru {}...",
        'reading_metadata': "Se citesc metadatele pentru {}...",
        'match_confidence': "Încredere potrivire: {}%",
        'file_too_large': "Dimensiune fișier: {} MB",
        'duration': "Durată: {} secunde",
        'metadata_diff': "Diferențe de metadate detectate",
        'content_diff': "Diferențe de conținut detectate",
        'proceed_with_sync': "Continuați cu sincronizarea? (d/n): ",
        'cancelled': "Operațiune anulată de utilizator.",
        'language_prompt': "Selectați limba (en/ro/ru): ",
        'new_folder': "Foldere noi (există în sursă, nu în țintă):",
        'removed_folder': "Foldere eliminate (există în țintă, nu în sursă):",
        'renamed_folder': "Foldere mutate/redenumite:",
    },
    'ru': {
        'welcome': "GnuLibrary - Синхронизация Музыкальной Коллекции",
        'select_source': "Выберите расположение ИСХОДНОГО хранилища:",
        'select_target': "Выберите расположение ЦЕЛЕВОГО хранилища:",
        'source_path': "Путь источника: {}",
        'target_path': "Путь цели: {}",
        'scanning': "Сканирование {}...",
        'analyzing': "Анализ файлов в {}...",
        'comparing': "Сравнение расположений хранилищ...",
        'found_files': "Найдено {} файлов в {}",
        'found_folders': "Найдено {} папок в {}",
        'changes_detected': "Обнаружены изменения:",
        'new_files': "Новые файлы (существуют в источнике, но не в цели):",
        'missing_files': "Отсутствующие файлы (существуют в цели, но не в источнике):",
        'moved_files': "Перемещенные/переименованные файлы:",
        'modified_files': "Измененные файлы (метаданные/контент изменены):",
        'folder_changes': "Изменения структуры папок:",
        'confirm_action': "Подтвердите действие для '{}':",
        'copy_file': "Копировать файл в цель",
        'delete_file': "Удалить файл из цели",
        'move_file': "Переместить/переименовать файл",
        'skip_file': "Пропустить этот файл",
        'apply_all_copy': "Применить КОПИРОВАНИЕ ко всем новым файлам",
        'apply_all_delete': "Применить УДАЛЕНИЕ ко всем отсутствующим файлам",
        'apply_all_move': "Применить ПЕРЕМЕЩЕНИЕ ко всем перемещенным файлам",
        'apply_all_skip': "ПРОПУСТИТЬ все остальные",
        'dry_run': "🧪 РЕЖИМ ТЕСТА - Изменения не будут внесены",
        'executing': "🚀 Выполнение изменений...",
        'completed': "✅ Операция синхронизации завершена!",
        'log_saved': "Журнал сохранен в: {}",
        'error': "❌ Ошибка: {}",
        'warning': "⚠️  Предупреждение: {}",
        'enter_path': "Введите путь {} (или 'browse' если GUI доступен): ",
        'invalid_path': "Неверный путь. Попробуйте снова.",
        'choose_action': "Выберите действие (1-4): ",
        'batch_prompt': "Пакетное действие? (д/н): ",
        'calculating_hash': "Вычисление хэша для {}...",
        'reading_metadata': "Чтение метаданных для {}...",
        'match_confidence': "Уверенность совпадения: {}%",
        'file_too_large': "Размер файла: {} МБ",
        'duration': "Продолжительность: {} секунд",
        'metadata_diff': "Обнаружены различия в метаданных",
        'content_diff': "Обнаружены различия в контенте",
        'proceed_with_sync': "Продолжить синхронизацию? (д/н): ",
        'cancelled': "Операция отменена пользователем.",
        'language_prompt': "Выберите язык (en/ro/ru): ",
        'new_folder': "Новые папки (существуют в источнике, но не в цели):",
        'removed_folder': "Удаленные папки (существуют в цели, но не в источнике):",
        'renamed_folder': "Переименованные/перемещенные папки:",
    }
}

def get_translation(lang_code, key, *args):
    """Get translated string with optional formatting arguments."""
    if lang_code not in TRANSLATIONS:
        lang_code = 'en'

    text = TRANSLATIONS[lang_code].get(key, TRANSLATIONS['en'].get(key, key))
    if args:
        return text.format(*args)
    return text

def add_translation(lang_code, translations_dict):
    """Add or update translations for a language."""
    if lang_code not in TRANSLATIONS:
        TRANSLATIONS[lang_code] = {}
    TRANSLATIONS[lang_code].update(translations_dict)

# ============================================================================
# FILE FINGERPRINTING AND METADATA ANALYSIS
# ============================================================================

class FileFingerprint:
    """Represents a comprehensive fingerprint of a file for comparison."""

    def __init__(self, filepath, base_path):
        self.filepath = Path(filepath)
        self.base_path = Path(base_path)
        self.relative_path = self.filepath.relative_to(self.base_path)
        self.size = 0
        self.mtime = 0
        self.hash_partial = None
        self.hash_full = None
        self.duration = None
        self.metadata = {}
        self.file_type = None
        self.error = None

        self._analyze()

    def _analyze(self):
        """Perform comprehensive file analysis."""
        try:
            if not self.filepath.exists():
                self.error = "File does not exist"
                return

            # Basic file properties
            stat_info = self.filepath.stat()
            self.size = stat_info.st_size
            self.mtime = stat_info.st_mtime

            # Determine file type
            ext = self.filepath.suffix.lower()
            self.file_type = ext

            # Calculate partial hash (first 1MB + last 1MB for large files)
            self._calculate_partial_hash()

            # Extract metadata for audio files
            if MUTAGEN_AVAILABLE and ext in ['.mp3', '.ogg', '.oga', '.flac', '.m4a', '.mp4']:
                self._extract_metadata()

        except Exception as e:
            self.error = str(e)

    def _calculate_partial_hash(self):
        """Calculate hash of file parts for quick comparison."""
        try:
            hasher = hashlib.md5()
            file_size = self.size

            with open(self.filepath, 'rb') as f:
                # Read first 1MB
                chunk = f.read(1024 * 1024)
                hasher.update(chunk)

                # For files larger than 2MB, also read last 1MB
                if file_size > 2 * 1024 * 1024:
                    f.seek(-1024 * 1024, 2)  # Seek from end
                    chunk = f.read(1024 * 1024)
                    hasher.update(chunk)

            self.hash_partial = hasher.hexdigest()

        except Exception as e:
            self.hash_partial = None

    def _extract_metadata(self):
        """Extract audio metadata using mutagen."""
        try:
            ext = self.file_type
            audio = None

            if ext == '.mp3':
                audio = MP3(str(self.filepath))
                if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                    self.duration = audio.info.length
            elif ext in ['.ogg', '.oga']:
                audio = OggVorbis(str(self.filepath))
                if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                    self.duration = audio.info.length
            elif ext == '.flac':
                audio = FLAC(str(self.filepath))
                if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                    self.duration = audio.info.length
            elif ext in ['.m4a', '.mp4']:
                audio = MP4(str(self.filepath))
                if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                    self.duration = audio.info.length

            # Extract common tags
            if audio and hasattr(audio, 'tags') and audio.tags:
                tags = audio.tags
                self.metadata = {
                    'title': str(tags.get('title', [''])[0]) if tags.get('title') else '',
                    'artist': str(tags.get('artist', [''])[0]) if tags.get('artist') else '',
                    'album': str(tags.get('album', [''])[0]) if tags.get('album') else '',
                    'genre': str(tags.get('genre', [''])[0]) if tags.get('genre') else '',
                    'year': str(tags.get('date', [''])[0]) if tags.get('date') else '',
                    'track': str(tags.get('tracknumber', [''])[0]) if tags.get('tracknumber') else '',
                }

        except Exception as e:
            self.metadata = {'error': str(e)}

    def calculate_full_hash(self):
        """Calculate full file hash (expensive operation)."""
        if self.hash_full:
            return self.hash_full

        try:
            hasher = hashlib.sha256()
            with open(self.filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            self.hash_full = hasher.hexdigest()
            return self.hash_full
        except Exception:
            return None

    def matches(self, other, threshold=0.8):
        """
        Determine if this file matches another file with given confidence.
        Returns tuple: (is_match, confidence_score, reason)
        """
        if self.error or other.error:
            return False, 0.0, "Error in file analysis"

        # Exact same relative path and hash
        if self.relative_path == other.relative_path and self.hash_partial == other.hash_partial:
            return True, 1.0, "Exact match (path + hash)"

        # Same size and partial hash
        if self.size == other.size and self.hash_partial == other.hash_partial:
            return True, 0.95, "Same size and partial hash"

        # Similar size and duration (for audio files)
        if self.file_type in ['.mp3', '.ogg', '.oga', '.flac', '.m4a', '.mp4'] and \
           other.file_type in ['.mp3', '.ogg', '.oga', '.flac', '.m4a', '.mp4']:

            size_diff = abs(self.size - other.size) / max(self.size, other.size, 1)
            duration_diff = 0
            if self.duration and other.duration:
                duration_diff = abs(self.duration - other.duration) / max(self.duration, other.duration, 1)

            if size_diff < 0.05 and duration_diff < 0.05:  # Within 5%
                # Check metadata similarity
                metadata_score = self._compare_metadata(other)
                confidence = 1.0 - max(size_diff, duration_diff) * 0.5 + metadata_score * 0.3
                confidence = min(confidence, 0.99)

                if confidence >= threshold:
                    return True, confidence, f"Audio match (size/duration/metadata: {confidence:.0%})"

        # Filename similarity (for potential renames)
        name_similarity = SequenceMatcher(None,
                                         self.filepath.name,
                                         other.filepath.name).ratio()

        if name_similarity > 0.7 and self.size == other.size:
            return True, 0.75, f"Name similarity ({name_similarity:.0%}) + same size"

        return False, 0.0, "No significant match"

    def _compare_metadata(self, other):
        """Compare metadata between two files, return similarity score 0-1."""
        if not self.metadata or not other.metadata:
            return 0.0

        matching_fields = 0
        total_fields = 0

        for field in ['title', 'artist', 'album', 'genre']:
            val1 = self.metadata.get(field, '').lower().strip()
            val2 = other.metadata.get(field, '').lower().strip()

            if val1 or val2:  # At least one has value
                total_fields += 1
                if val1 == val2:
                    matching_fields += 1
                elif val1 and val2:
                    # Partial match
                    similarity = SequenceMatcher(None, val1, val2).ratio()
                    if similarity > 0.8:
                        matching_fields += similarity

        return matching_fields / total_fields if total_fields > 0 else 0.0

    def to_dict(self):
        """Convert fingerprint to dictionary for logging."""
        return {
            'relative_path': str(self.relative_path),
            'size': self.size,
            'mtime': self.mtime,
            'hash_partial': self.hash_partial,
            'duration': self.duration,
            'metadata': self.metadata,
            'file_type': self.file_type,
            'error': self.error
        }

# ============================================================================
# STORAGE SCANNER
# ============================================================================

class StorageScanner:
    """Scans a storage location and builds a database of file fingerprints."""

    def __init__(self, base_path, lang='en', verbose=True):
        self.base_path = Path(base_path).resolve()
        self.lang = lang
        self.verbose = verbose
        self.files = {}  # relative_path -> FileFingerprint
        self.folders = set()
        self.errors = []

    def scan(self, progress_callback=None):
        """Scan the entire storage location."""
        if not self.base_path.exists():
            raise ValueError(f"Path does not exist: {self.base_path}")

        if self.verbose:
            print(get_translation(self.lang, 'scanning', str(self.base_path)))

        file_count = 0
        folder_count = 0

        # Use ThreadPoolExecutor for parallel scanning
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []

            for root, dirs, files in os.walk(self.base_path):
                # Track folders
                root_path = Path(root)
                rel_root = root_path.relative_to(self.base_path)

                if rel_root != Path('.'):
                    self.folders.add(str(rel_root))
                    folder_count += 1

                # Submit file analysis tasks
                for filename in files:
                    filepath = root_path / filename
                    future = executor.submit(self._analyze_file, filepath)
                    futures.append(future)
                    file_count += 1

                    if progress_callback and file_count % 100 == 0:
                        progress_callback(file_count, "files")

            # Collect results
            for i, future in enumerate(as_completed(futures)):
                try:
                    fingerprint = future.result()
                    if fingerprint and not fingerprint.error:
                        self.files[fingerprint.relative_path] = fingerprint
                    elif fingerprint and fingerprint.error:
                        self.errors.append((str(fingerprint.filepath), fingerprint.error))
                except Exception as e:
                    self.errors.append(("Unknown", str(e)))

                if progress_callback and (i + 1) % 100 == 0:
                    progress_callback(i + 1, f"of {len(futures)} analyzed")

        if self.verbose:
            print(get_translation(self.lang, 'found_files', len(self.files), str(self.base_path)))
            print(get_translation(self.lang, 'found_folders', len(self.folders), str(self.base_path)))

        return len(self.files), len(self.folders)

    def _analyze_file(self, filepath):
        """Analyze a single file (called in thread)."""
        try:
            return FileFingerprint(filepath, self.base_path)
        except Exception as e:
            fp = FileFingerprint.__new__(FileFingerprint)
            fp.filepath = filepath
            fp.base_path = self.base_path
            fp.relative_path = filepath.relative_to(self.base_path)
            fp.error = str(e)
            return fp

# ============================================================================
# COMPARISON ENGINE
# ============================================================================

class ChangeType:
    NEW_FILE = "new_file"
    MISSING_FILE = "missing_file"
    MOVED_FILE = "moved_file"
    MODIFIED_FILE = "modified_file"
    NEW_FOLDER = "new_folder"
    REMOVED_FOLDER = "removed_folder"
    MOVED_FOLDER = "moved_folder"

class SyncChange:
    """Represents a single change detected between two storages."""

    def __init__(self, change_type, source_item=None, target_item=None,
                 confidence=1.0, reason="", metadata_diff=None):
        self.change_type = change_type
        self.source_item = source_item  # FileFingerprint or folder path
        self.target_item = target_item  # FileFingerprint or folder path
        self.confidence = confidence
        self.reason = reason
        self.metadata_diff = metadata_diff or {}
        self.user_action = None  # Will be set by user interaction
        self.applied = False

    def __str__(self):
        if self.change_type == ChangeType.NEW_FILE:
            return f"NEW: {self.source_item.relative_path}"
        elif self.change_type == ChangeType.MISSING_FILE:
            return f"MISSING: {self.target_item.relative_path}"
        elif self.change_type == ChangeType.MOVED_FILE:
            return f"MOVED: {self.target_item.relative_path} → {self.source_item.relative_path}"
        elif self.change_type == ChangeType.MODIFIED_FILE:
            return f"MODIFIED: {self.source_item.relative_path}"
        elif self.change_type == ChangeType.NEW_FOLDER:
            return f"NEW FOLDER: {self.source_item}"
        elif self.change_type == ChangeType.REMOVED_FOLDER:
            return f"REMOVED FOLDER: {self.target_item}"
        elif self.change_type == ChangeType.MOVED_FOLDER:
            return f"MOVED FOLDER: {self.target_item} → {self.source_item}"
        return f"UNKNOWN: {self.change_type}"

class ComparisonEngine:
    """Compares two storage scanners and identifies all changes."""

    def __init__(self, source_scanner, target_scanner, lang='en', verbose=True):
        self.source = source_scanner
        self.target = target_scanner
        self.lang = lang
        self.verbose = verbose
        self.changes = []

    def compare(self, progress_callback=None):
        """Perform comprehensive comparison."""
        if self.verbose:
            print(get_translation(self.lang, 'comparing'))

        # Track processed items to avoid duplicates
        processed_source = set()
        processed_target = set()

        source_files = dict(self.source.files)
        target_files = dict(self.target.files)

        total_comparisons = len(source_files) + len(target_files)
        current = 0

        # Step 1: Find exact and near matches
        for src_path, src_fp in source_files.items():
            if src_path in target_files:
                # Same relative path exists
                tgt_fp = target_files[src_path]
                processed_source.add(src_path)
                processed_target.add(src_path)

                # Check if modified
                is_same, confidence, reason = src_fp.matches(tgt_fp)
                if not is_same:
                    # Analyze what changed
                    metadata_diff = self._compare_metadata(src_fp, tgt_fp)
                    content_changed = src_fp.hash_partial != tgt_fp.hash_partial

                    change = SyncChange(
                        ChangeType.MODIFIED_FILE,
                        source_item=src_fp,
                        target_item=tgt_fp,
                        confidence=confidence,
                        reason=reason,
                        metadata_diff=metadata_diff
                    )
                    self.changes.append(change)
            else:
                # Look for moved/renamed file
                best_match = None
                best_confidence = 0
                best_reason = ""

                for tgt_path, tgt_fp in target_files.items():
                    if tgt_path in processed_target:
                        continue

                    is_match, confidence, reason = src_fp.matches(tgt_fp)
                    if is_match and confidence > best_confidence:
                        best_match = tgt_fp
                        best_confidence = confidence
                        best_reason = reason

                if best_match and best_confidence > 0.7:
                    # Found a move/rename
                    processed_source.add(src_path)
                    processed_target.add(best_match.relative_path)

                    change = SyncChange(
                        ChangeType.MOVED_FILE,
                        source_item=src_fp,
                        target_item=best_match,
                        confidence=best_confidence,
                        reason=best_reason
                    )
                    self.changes.append(change)
                else:
                    # New file in source
                    processed_source.add(src_path)
                    change = SyncChange(
                        ChangeType.NEW_FILE,
                        source_item=src_fp,
                        confidence=1.0,
                        reason="Exists in source only"
                    )
                    self.changes.append(change)

            current += 1
            if progress_callback and current % 100 == 0:
                progress_callback(current, total_comparisons)

        # Step 2: Find missing files (in target but not matched in source)
        for tgt_path, tgt_fp in target_files.items():
            if tgt_path not in processed_target:
                processed_target.add(tgt_path)
                change = SyncChange(
                    ChangeType.MISSING_FILE,
                    target_item=tgt_fp,
                    confidence=1.0,
                    reason="Exists in target only"
                )
                self.changes.append(change)

        # Step 3: Compare folder structures
        self._compare_folders()

        # Sort changes by type for better presentation
        type_order = [
            ChangeType.NEW_FOLDER,
            ChangeType.REMOVED_FOLDER,
            ChangeType.MOVED_FOLDER,
            ChangeType.NEW_FILE,
            ChangeType.MISSING_FILE,
            ChangeType.MOVED_FILE,
            ChangeType.MODIFIED_FILE,
        ]

        self.changes.sort(key=lambda c: (type_order.index(c.change_type) if c.change_type in type_order else 99, str(c)))

        if self.verbose:
            print(get_translation(self.lang, 'changes_detected'))
            for change in self.changes[:10]:  # Show first 10
                print(f"  {change}")
            if len(self.changes) > 10:
                print(f"  ... and {len(self.changes) - 10} more changes")

        return self.changes

    def _compare_metadata(self, src_fp, tgt_fp):
        """Compare metadata between two files, return differences dict."""
        diff = {}

        for field in ['title', 'artist', 'album', 'genre', 'year', 'track']:
            src_val = src_fp.metadata.get(field, '')
            tgt_val = tgt_fp.metadata.get(field, '')

            if src_val != tgt_val:
                diff[field] = {'source': src_val, 'target': tgt_val}

        if src_fp.duration and tgt_fp.duration:
            if abs(src_fp.duration - tgt_fp.duration) > 0.1:
                diff['duration'] = {'source': src_fp.duration, 'target': tgt_fp.duration}

        return diff

    def _compare_folders(self):
        """Compare folder structures."""
        source_folders = self.source.folders
        target_folders = self.target.folders

        # New folders in source
        for folder in source_folders:
            if folder not in target_folders:
                self.changes.append(SyncChange(
                    ChangeType.NEW_FOLDER,
                    source_item=folder,
                    confidence=1.0,
                    reason="Folder exists in source only"
                ))

        # Removed folders (in target but not source)
        for folder in target_folders:
            if folder not in source_folders:
                self.changes.append(SyncChange(
                    ChangeType.REMOVED_FOLDER,
                    target_item=folder,
                    confidence=1.0,
                    reason="Folder exists in target only"
                ))

# ============================================================================
# USER INTERACTION MANAGER
# ============================================================================

class InteractionManager:
    """Handles all user interactions for decision making."""

    def __init__(self, lang='en'):
        self.lang = lang
        self.batch_actions = {}

    def select_folder_gui(self, title):
        """Open GUI folder selector if tkinter available."""
        if not TKINTER_AVAILABLE:
            return None

        root = tk.Tk()
        root.withdraw()  # Hide main window
        root.attributes('-topmost', True)  # Bring to front

        folder_path = filedialog.askdirectory(title=title)
        root.destroy()

        return folder_path if folder_path else None

    def get_path_input(self, prompt_key):
        """Get path from user via CLI or GUI."""
        while True:
            if TKINTER_AVAILABLE:
                user_input = input(get_translation(self.lang, 'enter_path', prompt_key)).strip()
                if user_input.lower() == 'browse':
                    path = self.select_folder_gui(get_translation(self.lang, 'select_' + prompt_key))
                    if path:
                        return path
                elif user_input:
                    if os.path.isdir(user_input):
                        return os.path.abspath(user_input)
                    else:
                        print(get_translation(self.lang, 'invalid_path'))
            else:
                try:
                    path = input(get_translation(self.lang, 'enter_path', prompt_key)).strip()
                    if os.path.isdir(path):
                        return os.path.abspath(path)
                    else:
                        print(get_translation(self.lang, 'invalid_path'))
                except EOFError:
                    print("\nInput ended unexpectedly. Exiting.")
                    sys.exit(1)

    def present_change(self, change, index, total):
        """Present a single change to user and get decision."""
        print("\n" + "=" * 60)
        print(f"[{index}/{total}] {change.change_type.upper()}")
        print("=" * 60)

        if change.change_type in [ChangeType.NEW_FILE, ChangeType.MODIFIED_FILE]:
            item = change.source_item
            print(f"File: {item.relative_path}")
            print(f"Size: {item.size / 1024 / 1024:.2f} MB")
            if item.duration:
                print(f"Duration: {item.duration:.1f}s")
            if item.metadata.get('title'):
                print(f"Title: {item.metadata['title']}")
            if item.metadata.get('artist'):
                print(f"Artist: {item.metadata['artist']}")

            print("\nActions:")
            print("1. " + get_translation(self.lang, 'copy_file'))
            if change.change_type == ChangeType.MODIFIED_FILE:
                print("2. Keep target version (skip)")
            else:
                print("2. " + get_translation(self.lang, 'skip_file'))
            print("3. " + get_translation(self.lang, 'apply_all_copy'))
            print("4. " + get_translation(self.lang, 'apply_all_skip'))

            while True:
                try:
                    choice = input(get_translation(self.lang, 'choose_action')).strip()
                    if choice == '1':
                        change.user_action = 'copy'
                        break
                    elif choice == '2':
                        change.user_action = 'skip'
                        break
                    elif choice == '3':
                        self.batch_actions['new'] = 'copy'
                        change.user_action = 'copy'
                        break
                    elif choice == '4':
                        self.batch_actions['new'] = 'skip'
                        change.user_action = 'skip'
                        break
                except EOFError:
                    print("\nInput ended. Exiting.")
                    sys.exit(1)

        elif change.change_type == ChangeType.MISSING_FILE:
            item = change.target_item
            print(f"File: {item.relative_path}")
            print(f"Size: {item.size / 1024 / 1024:.2f} MB")

            print("\nActions:")
            print("1. " + get_translation(self.lang, 'delete_file'))
            print("2. " + get_translation(self.lang, 'skip_file'))
            print("3. " + get_translation(self.lang, 'apply_all_delete'))
            print("4. " + get_translation(self.lang, 'apply_all_skip'))

            while True:
                try:
                    choice = input(get_translation(self.lang, 'choose_action')).strip()
                    if choice == '1':
                        change.user_action = 'delete'
                        break
                    elif choice == '2':
                        change.user_action = 'skip'
                        break
                    elif choice == '3':
                        self.batch_actions['missing'] = 'delete'
                        change.user_action = 'delete'
                        break
                    elif choice == '4':
                        self.batch_actions['missing'] = 'skip'
                        change.user_action = 'skip'
                        break
                except EOFError:
                    print("\nInput ended. Exiting.")
                    sys.exit(1)

        elif change.change_type == ChangeType.MOVED_FILE:
            print(f"From: {change.target_item.relative_path}")
            print(f"To: {change.source_item.relative_path}")
            print(f"Confidence: {change.confidence:.0%}")
            print(f"Reason: {change.reason}")

            print("\nActions:")
            print("1. " + get_translation(self.lang, 'move_file'))
            print("2. " + get_translation(self.lang, 'skip_file'))
            print("3. " + get_translation(self.lang, 'apply_all_move'))
            print("4. " + get_translation(self.lang, 'apply_all_skip'))

            while True:
                try:
                    choice = input(get_translation(self.lang, 'choose_action')).strip()
                    if choice == '1':
                        change.user_action = 'move'
                        break
                    elif choice == '2':
                        change.user_action = 'skip'
                        break
                    elif choice == '3':
                        self.batch_actions['moved'] = 'move'
                        change.user_action = 'move'
                        break
                    elif choice == '4':
                        self.batch_actions['moved'] = 'skip'
                        change.user_action = 'skip'
                        break
                except EOFError:
                    print("\nInput ended. Exiting.")
                    sys.exit(1)

        elif change.change_type in [ChangeType.NEW_FOLDER, ChangeType.REMOVED_FOLDER, ChangeType.MOVED_FOLDER]:
            if change.change_type == ChangeType.NEW_FOLDER:
                print(f"New folder: {change.source_item}")
                action_desc = "Create folder"
            elif change.change_type == ChangeType.REMOVED_FOLDER:
                print(f"Removed folder: {change.target_item}")
                action_desc = "Remove folder"
            else:
                print(f"From: {change.target_item}")
                print(f"To: {change.source_item}")
                action_desc = "Move folder"

            print("\nActions:")
            print(f"1. {action_desc}")
            print("2. Skip")

            while True:
                try:
                    choice = input(get_translation(self.lang, 'choose_action')).strip()
                    if choice == '1':
                        change.user_action = 'apply'
                        break
                    elif choice == '2':
                        change.user_action = 'skip'
                        break
                except EOFError:
                    print("\nInput ended. Exiting.")
                    sys.exit(1)

        return change.user_action

    def apply_batch_action(self, change):
        """Apply batch action if available."""
        batch_map = {
            ChangeType.NEW_FILE: self.batch_actions.get('new'),
            ChangeType.MISSING_FILE: self.batch_actions.get('missing'),
            ChangeType.MOVED_FILE: self.batch_actions.get('moved'),
        }

        batch_action = batch_map.get(change.change_type)
        if batch_action:
            change.user_action = batch_action
            return True
        return False

    def confirm_sync(self, changes):
        """Ask user to confirm proceeding with sync."""
        pending = sum(1 for c in changes if c.user_action and c.user_action != 'skip')

        if pending == 0:
            print("\nNo actions selected. Nothing to do.")
            return False

        print(f"\n{pending} changes will be applied.")
        response = input(get_translation(self.lang, 'proceed_with_sync')).strip().lower()
        return response in ['y', 'yes', 'д', 'да']

# ============================================================================
# SYNC EXECUTOR
# ============================================================================

class SyncExecutor:
    """Executes the approved sync changes."""

    def __init__(self, source_path, target_path, lang='en', dry_run=False, verbose=True):
        self.source_path = Path(source_path)
        self.target_path = Path(target_path)
        self.lang = lang
        self.dry_run = dry_run
        self.verbose = verbose
        self.log_entries = []

    def execute(self, changes):
        """Execute all approved changes."""
        if self.dry_run:
            print("\n" + get_translation(self.lang, 'dry_run'))

        if self.verbose:
            print(get_translation(self.lang, 'executing'))

        success_count = 0
        error_count = 0

        for i, change in enumerate(changes, 1):
            if not change.user_action or change.user_action == 'skip':
                continue

            try:
                if self.dry_run:
                    print(f"[DRY RUN] Would {change.user_action}: {change}")
                    success_count += 1
                else:
                    self._execute_change(change)
                    change.applied = True
                    success_count += 1
                    self._log_change(change, "SUCCESS")
            except Exception as e:
                error_count += 1
                self._log_change(change, f"ERROR: {e}")
                print(get_translation(self.lang, 'error', str(e)))

        if self.verbose:
            print(f"\nCompleted: {success_count} successful, {error_count} errors")

        return success_count, error_count

    def _execute_change(self, change):
        """Execute a single change."""
        if change.change_type == ChangeType.NEW_FILE:
            src_file = self.source_path / change.source_item.relative_path
            tgt_file = self.target_path / change.source_item.relative_path

            # Create parent directories
            tgt_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(str(src_file), str(tgt_file))

        elif change.change_type == ChangeType.MISSING_FILE:
            tgt_file = self.target_path / change.target_item.relative_path

            if tgt_file.exists():
                tgt_file.unlink()

        elif change.change_type == ChangeType.MOVED_FILE:
            old_file = self.target_path / change.target_item.relative_path
            new_file = self.target_path / change.source_item.relative_path

            # Create parent directories
            new_file.parent.mkdir(parents=True, exist_ok=True)

            if old_file.exists():
                shutil.move(str(old_file), str(new_file))
            else:
                # Source doesn't exist, copy from source storage
                src_file = self.source_path / change.source_item.relative_path
                if src_file.exists():
                    shutil.copy2(str(src_file), str(new_file))

        elif change.change_type == ChangeType.MODIFIED_FILE:
            src_file = self.source_path / change.source_item.relative_path
            tgt_file = self.target_path / change.source_item.relative_path

            if change.user_action == 'copy':
                shutil.copy2(str(src_file), str(tgt_file))

        elif change.change_type == ChangeType.NEW_FOLDER:
            folder_path = self.target_path / change.source_item
            folder_path.mkdir(parents=True, exist_ok=True)

        elif change.change_type == ChangeType.REMOVED_FOLDER:
            folder_path = self.target_path / change.target_item
            if folder_path.exists():
                shutil.rmtree(str(folder_path))

        elif change.change_type == ChangeType.MOVED_FOLDER:
            old_path = self.target_path / change.target_item
            new_path = self.target_path / change.source_item

            if old_path.exists():
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_path), str(new_path))

    def _log_change(self, change, status):
        """Log a change execution."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'change_type': change.change_type,
            'description': str(change),
            'action': change.user_action,
            'status': status,
        }
        self.log_entries.append(entry)

    def save_log(self, target_path=None):
        """Save execution log to file."""
        if not target_path:
            target_path = self.target_path

        log_file = Path(target_path) / f"sync_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        log_data = {
            'sync_time': datetime.now().isoformat(),
            'source': str(self.source_path),
            'target': str(self.target_path),
            'dry_run': self.dry_run,
            'changes': self.log_entries,
        }

        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        return str(log_file)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class MusicSyncApp:
    """Main application orchestrator."""

    def __init__(self):
        self.lang = 'en'
        self.dry_run = False
        self.verbose = True
        self.source_path = None
        self.target_path = None
        self.interaction = None

    def select_language(self):
        """Let user select language."""
        print("\nAvailable languages: en (English), ro (Română), ru (Русский)")
        while True:
            lang = input(get_translation('en', 'language_prompt')).strip().lower()
            if lang in ['en', 'english']:
                self.lang = 'en'
                break
            elif lang in ['ro', 'romana', 'română']:
                self.lang = 'ro'
                break
            elif lang in ['ru', 'russian', 'русский']:
                self.lang = 'ru'
                break
            else:
                print("Invalid choice, defaulting to English.")
                self.lang = 'en'
                break

    def run(self):
        """Run the main application loop."""
        # Initialize interaction manager early
        self.interaction = InteractionManager(self.lang)

        print("\n" + "=" * 60)
        print(get_translation(self.lang, 'welcome'))
        print("=" * 60)

        # Language selection
        self.select_language()

        # Update interaction manager with selected language
        self.interaction.lang = self.lang

        # Get paths
        print("\n" + get_translation(self.lang, 'select_source'))
        self.source_path = self.interaction.get_path_input('source')

        print("\n" + get_translation(self.lang, 'select_target'))
        self.target_path = self.interaction.get_path_input('target')

        print(get_translation(self.lang, 'source_path', self.source_path))
        print(get_translation(self.lang, 'target_path', self.target_path))

        # Scan source
        print("\n")
        source_scanner = StorageScanner(self.source_path, self.lang, self.verbose)
        source_scanner.scan()

        # Scan target
        print("\n")
        target_scanner = StorageScanner(self.target_path, self.lang, self.verbose)
        target_scanner.scan()

        # Compare
        print("\n")
        engine = ComparisonEngine(source_scanner, target_scanner, self.lang, self.verbose)
        changes = engine.compare()

        if not changes:
            print("\n✅ No changes detected. Storages are in sync!")
            return

        # Interactive review
        print("\n" + "=" * 60)
        print("REVIEW CHANGES")
        print("=" * 60)

        self.interaction = InteractionManager(self.lang)

        for i, change in enumerate(changes, 1):
            # Check for batch action first
            if not self.interaction.apply_batch_action(change):
                self.interaction.present_change(change, i, len(changes))

        # Confirm
        if not self.interaction.confirm_sync(changes):
            print(get_translation(self.lang, 'cancelled'))
            return

        # Execute
        executor = SyncExecutor(
            self.source_path,
            self.target_path,
            self.lang,
            self.dry_run,
            self.verbose
        )

        success, errors = executor.execute(changes)

        # Save log
        if not self.dry_run:
            log_path = executor.save_log()
            print(get_translation(self.lang, 'log_saved', log_path))

        print("\n" + get_translation(self.lang, 'completed'))

def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description='GnuLibrary - Smart file synchronization for music collections'
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Perform a test run without making changes')
    parser.add_argument('--no-verbose', action='store_true',
                       help='Reduce output verbosity')
    parser.add_argument('--lang', choices=['en', 'ro', 'ru'], default='en',
                       help='Language preference')

    args = parser.parse_args()

    app = MusicSyncApp()
    app.dry_run = args.dry_run
    app.verbose = not args.no_verbose
    app.lang = args.lang

    try:
        app.run()
    except KeyboardInterrupt:
        print("\n\nOperation interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
