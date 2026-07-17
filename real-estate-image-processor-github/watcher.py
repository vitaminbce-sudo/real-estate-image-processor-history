import os
import time
import threading
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from processor import process_image, expected_output_paths


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff"
}

SKIP_DIR_NAMES = {
    "HP",
    "SUUMO"
}


def is_image_file(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def contains_output_folder(path: str) -> bool:
    """
    無限ループ防止。
    パス内に HP または SUUMO が含まれる場合は絶対に処理しない。
    """
    parts = Path(path).parts
    return any(part.upper() in SKIP_DIR_NAMES for part in parts)


def wait_until_file_is_ready(path: str, timeout: float = 15.0, interval: float = 0.5) -> bool:
    """
    コピー途中の画像を処理しないよう、ファイルサイズが安定するまで待つ。
    """
    start = time.time()
    previous_size = -1

    while time.time() - start < timeout:
        if not os.path.exists(path):
            time.sleep(interval)
            continue

        try:
            current_size = os.path.getsize(path)
        except OSError:
            time.sleep(interval)
            continue

        if current_size > 0 and current_size == previous_size:
            return True

        previous_size = current_size
        time.sleep(interval)

    return False


class PropertyImageEventHandler(FileSystemEventHandler):
    def __init__(self, watch_folder: str, log_callback=None):
        super().__init__()
        self.watch_folder = os.path.abspath(watch_folder)
        self.log_callback = log_callback

        self._processing_paths = set()
        self._lock = threading.Lock()

    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def on_created(self, event):
        if event.is_directory:
            self._handle_directory_event(event.src_path)
        else:
            self._handle_file_event(event.src_path, reason="[CREATE]")

    def on_modified(self, event):
        if event.is_directory:
            return

        self._handle_file_event(event.src_path, reason="[MODIFY]")

    def on_moved(self, event):
        dest_path = getattr(event, "dest_path", None)

        if not dest_path:
            return

        if event.is_directory:
            self._handle_directory_event(dest_path)
        else:
            self._handle_file_event(dest_path, reason="[MOVED]")

    def process_existing_property_folders(self):
        """
        監視開始時に、既存の物件フォルダを確認する。
        HP / SUUMO の出力がなければ処理。
        """
        if not os.path.isdir(self.watch_folder):
            self.log(f"[ERROR] 監視フォルダが存在しません: {self.watch_folder}")
            return

        self.log("[SCAN] 既存物件フォルダの確認開始")

        try:
            entries = list(os.scandir(self.watch_folder))
        except OSError as e:
            self.log(f"[ERROR] 既存フォルダ確認に失敗: {self.watch_folder} / {e}")
            return

        count = 0

        for entry in entries:
            if not entry.is_dir():
                continue

            if entry.name.upper() in SKIP_DIR_NAMES:
                continue

            property_folder = os.path.abspath(entry.path)

            processed = self._scan_and_process_property_folder(
                property_folder=property_folder,
                reason="[INITIAL]"
            )

            count += processed

        self.log(f"[SCAN] 既存物件フォルダの確認完了: {count}件処理")

    def _handle_directory_event(self, dir_path: str):
        dir_path = os.path.abspath(dir_path)

        if contains_output_folder(dir_path):
            return

        property_folder = self._get_property_folder_from_any_path(dir_path)

        if property_folder is None:
            return

        thread = threading.Thread(
            target=self._delayed_scan_property_folder,
            args=(property_folder,),
            daemon=True
        )
        thread.start()

    def _delayed_scan_property_folder(self, property_folder: str):
        time.sleep(1.0)

        self._scan_and_process_property_folder(
            property_folder=property_folder,
            reason="[DIR]"
        )

    def _handle_file_event(self, src_path: str, reason: str):
        src_path = os.path.abspath(src_path)

        if contains_output_folder(src_path):
            self.log(f"{reason} [SKIP] 出力フォルダ内: {src_path}")
            return

        if not is_image_file(src_path):
            return

        property_folder = self._get_property_folder_from_image_path(src_path)

        if property_folder is None:
            return

        self._process_single_image(
            src_path=src_path,
            property_folder=property_folder,
            reason=reason
        )

    def _scan_and_process_property_folder(self, property_folder: str, reason: str) -> int:
        property_folder = os.path.abspath(property_folder)

        if not os.path.isdir(property_folder):
            return 0

        if contains_output_folder(property_folder):
            return 0

        image_paths = []

        for root, dirs, files in os.walk(property_folder):
            dirs[:] = [
                d for d in dirs
                if d.upper() not in SKIP_DIR_NAMES
            ]

            if contains_output_folder(root):
                continue

            for filename in files:
                path = os.path.join(root, filename)

                if contains_output_folder(path):
                    continue

                if is_image_file(path):
                    image_paths.append(os.path.abspath(path))

        processed_count = 0

        for image_path in sorted(image_paths):
            success = self._process_single_image(
                src_path=image_path,
                property_folder=property_folder,
                reason=reason
            )

            if success:
                processed_count += 1

        if image_paths:
            self.log(f"{reason} 物件フォルダ確認: {processed_count}/{len(image_paths)}件処理 - {property_folder}")

        return processed_count

    def _process_single_image(self, src_path: str, property_folder: str, reason: str) -> bool:
        src_path = os.path.abspath(src_path)
        property_folder = os.path.abspath(property_folder)

        if contains_output_folder(src_path):
            return False

        if not is_image_file(src_path):
            return False

        normalized_key = os.path.normcase(src_path)

        with self._lock:
            if normalized_key in self._processing_paths:
                return False

            self._processing_paths.add(normalized_key)

        try:
            if not wait_until_file_is_ready(src_path):
                self.log(f"{reason} [SKIP] 読み込み準備未完了: {src_path}")
                return False

            if not self._needs_processing(src_path, property_folder):
                return False

            self.log(f"{reason} [PROCESS] 処理開始: {src_path}")

            process_image(
                input_path=src_path,
                property_folder=property_folder
            )

            self.log(f"{reason} [DONE] 処理完了: {src_path}")
            return True

        except Exception as e:
            self.log(f"{reason} [ERROR] {src_path} / {e}")
            return False

        finally:
            with self._lock:
                self._processing_paths.discard(normalized_key)

    def _needs_processing(self, src_path: str, property_folder: str) -> bool:
        """
        HP / SUUMO の出力が両方あり、かつ元画像より新しければ処理しない。
        片方でもない場合や、元画像の方が新しい場合は処理する。
        """
        paths = expected_output_paths(src_path, property_folder)

        try:
            src_mtime = os.path.getmtime(src_path)
        except OSError:
            return False

        for output_path in paths.values():
            if not os.path.exists(output_path):
                return True

            try:
                output_mtime = os.path.getmtime(output_path)
            except OSError:
                return True

            if output_mtime < src_mtime:
                return True

        return False

    def _get_property_folder_from_image_path(self, src_path: str):
        if not self._is_under_watch_folder(src_path):
            return None

        try:
            relative_path = os.path.relpath(src_path, self.watch_folder)
        except ValueError:
            return None

        relative_parts = Path(relative_path).parts

        # 監視フォルダ直下の画像は処理しない
        if len(relative_parts) < 2:
            self.log(f"[SKIP] 物件フォルダ外: {src_path}")
            return None

        property_folder_name = relative_parts[0]

        if property_folder_name.upper() in SKIP_DIR_NAMES:
            return None

        return os.path.abspath(os.path.join(self.watch_folder, property_folder_name))

    def _get_property_folder_from_any_path(self, path: str):
        if not self._is_under_watch_folder(path):
            return None

        try:
            relative_path = os.path.relpath(path, self.watch_folder)
        except ValueError:
            return None

        if relative_path in (".", ""):
            return None

        relative_parts = Path(relative_path).parts

        if not relative_parts:
            return None

        property_folder_name = relative_parts[0]

        if property_folder_name.upper() in SKIP_DIR_NAMES:
            return None

        return os.path.abspath(os.path.join(self.watch_folder, property_folder_name))

    def _is_under_watch_folder(self, path: str) -> bool:
        try:
            watch = os.path.normcase(os.path.abspath(self.watch_folder))
            target = os.path.normcase(os.path.abspath(path))
            common = os.path.commonpath([watch, target])
            return common == watch
        except ValueError:
            return False


class ImageFolderWatcher:
    def __init__(self, watch_folder: str, log_callback=None):
        self.watch_folder = os.path.abspath(watch_folder)
        self.log_callback = log_callback
        self.observer = None

    def start(self):
        event_handler = PropertyImageEventHandler(
            watch_folder=self.watch_folder,
            log_callback=self.log_callback
        )

        self.observer = Observer()
        self.observer.schedule(
            event_handler,
            self.watch_folder,
            recursive=True
        )

        self.observer.start()

        # 既存フォルダを起動時に確認
        event_handler.process_existing_property_folders()

        try:
            while self.observer.is_alive():
                time.sleep(0.5)
        finally:
            self.stop()

    def stop(self):
        if self.observer is not None:
            self.observer.stop()
            self.observer.join(timeout=3)
            self.observer = None