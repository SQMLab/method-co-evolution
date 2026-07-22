import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from pathlib import Path

import pandas as pd
from pandas import DataFrame

import mhc.util as util
from mhc.artifacts import is_test_case_method
from mhc.method_scanner import (
    DEFAULT_SCAN_MERGE_THRESHOLD,
    SCAN_SLOW_SECONDS,
    _append_dataframe_csv,
    _log_scan_cache_filter,
    _log_scan_repository_start,
    _log_slow_operation,
    _maybe_log_scan_progress,
    _should_flush_scan_cache,
    _write_dataframe_csv,
    clone_and_checkout_commit,
    collect_files,
)
from mhc.zip import file_lock, remove_empty_directory_tree, remove_file_if_exists

METHOD_METADATA_COLUMNS = [
    "project",
    "name",
    "url",
    "annotations",
    "annotations_fqn",
    "frameworks",
    "javadoc",
]
METHOD_METADATA_FILE_COLUMN = "file"
METHOD_METADATA_HASH_COLUMN = "hash"
METHOD_METADATA_FLAG_COLUMN = "_flag"
METHOD_METADATA_ERROR_COLUMN = "_error"
METHOD_METADATA_MARKER = "__scan_marker__"
METHOD_METADATA_ERROR_MARKER = "__error_marker__"
METHOD_METADATA_ERROR_MAX_LENGTH = 256
METHOD_METADATA_CACHE_COLUMNS = METHOD_METADATA_COLUMNS + [
    METHOD_METADATA_FILE_COLUMN,
    METHOD_METADATA_HASH_COLUMN,
    METHOD_METADATA_FLAG_COLUMN,
    METHOD_METADATA_ERROR_COLUMN,
]
METHOD_METADATA_FLUSH_INTERVAL_SECONDS = 15 * 60


def _empty_metadata_row(repository_name: str, file: str, commit_hash: str) -> dict:
    row = {column: None for column in METHOD_METADATA_COLUMNS}
    row["project"] = repository_name
    row[METHOD_METADATA_FILE_COLUMN] = file
    row[METHOD_METADATA_HASH_COLUMN] = commit_hash
    row[METHOD_METADATA_FLAG_COLUMN] = None
    row[METHOD_METADATA_ERROR_COLUMN] = None
    return row


def _build_metadata_marker(repository_name: str, file: str, commit_hash: str) -> dict:
    row = _empty_metadata_row(repository_name, file, commit_hash)
    row[METHOD_METADATA_FLAG_COLUMN] = METHOD_METADATA_MARKER
    return row


def _build_metadata_error(
    repository_name: str,
    file: str,
    commit_hash: str,
    error: Exception | str | None = None,
) -> dict:
    row = _empty_metadata_row(repository_name, file, commit_hash)
    row[METHOD_METADATA_FLAG_COLUMN] = METHOD_METADATA_ERROR_MARKER
    if error is not None:
        row[METHOD_METADATA_ERROR_COLUMN] = str(error)[:METHOD_METADATA_ERROR_MAX_LENGTH]
    return row


def _read_metadata_cache(cache_file: str) -> pd.DataFrame:
    if not os.path.exists(cache_file):
        return pd.DataFrame(columns=METHOD_METADATA_CACHE_COLUMNS)
    try:
        cache_df = pd.read_csv(cache_file, dtype=str)
        if not set(METHOD_METADATA_CACHE_COLUMNS).issubset(cache_df.columns):
            return pd.DataFrame(columns=METHOD_METADATA_CACHE_COLUMNS)
        return cache_df.reindex(columns=METHOD_METADATA_CACHE_COLUMNS)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=METHOD_METADATA_CACHE_COLUMNS)


def _metadata_cache_schema_current(cache_file: str) -> bool:
    if not os.path.exists(cache_file):
        return True
    try:
        columns = pd.read_csv(cache_file, nrows=0).columns
    except pd.errors.EmptyDataError:
        return False
    return set(METHOD_METADATA_CACHE_COLUMNS).issubset(columns)


def _completed_metadata_files(cache_df: pd.DataFrame, retry_errors: bool = True) -> set[str]:
    if cache_df.empty:
        return set()
    rows = cache_df
    if retry_errors:
        rows = rows[rows[METHOD_METADATA_FLAG_COLUMN] != METHOD_METADATA_ERROR_MARKER]
    return set(rows[METHOD_METADATA_FILE_COLUMN].dropna().astype(str))


def _tried_metadata_files(cache_df: pd.DataFrame) -> set[str]:
    if cache_df.empty:
        return set()
    return set(cache_df[METHOD_METADATA_FILE_COLUMN].dropna().astype(str))


def _failed_metadata_files(cache_df: pd.DataFrame) -> set[str]:
    if cache_df.empty:
        return set()
    completed_files = _completed_metadata_files(cache_df)
    error_files = set(
        cache_df.loc[
            cache_df[METHOD_METADATA_FLAG_COLUMN] == METHOD_METADATA_ERROR_MARKER,
            METHOD_METADATA_FILE_COLUMN,
        ].dropna().astype(str)
    )
    return error_files - completed_files


def _load_cached_metadata_files(cache_file: str, retry_errors: bool = True) -> set[str]:
    return _completed_metadata_files(_read_metadata_cache(cache_file), retry_errors)


def _flush_metadata_rows(
    cache_file: str,
    lock_path: str,
    pending: list[dict],
    retry_errors: bool = True,
) -> None:
    if not pending:
        return
    rows = list(pending)
    pending.clear()
    with file_lock(lock_path):
        completed_files = _completed_metadata_files(
            _read_metadata_cache(cache_file),
            retry_errors,
        )
        rows = [
            row for row in rows
            if row.get(METHOD_METADATA_FILE_COLUMN) not in completed_files
        ]
        _append_dataframe_csv(
            cache_file,
            rows,
            METHOD_METADATA_CACHE_COLUMNS,
            [],
        )


def _is_metadata_output_current(output_file: str, commit_hash: str) -> bool:
    if not os.path.exists(output_file):
        return False
    try:
        output_df = pd.read_csv(output_file, usecols=["url", "frameworks"])
    except (ValueError, pd.errors.EmptyDataError):
        return False
    urls = output_df["url"].dropna().astype(str)
    return urls.empty or urls.str.contains(f"/blob/{commit_hash}/", regex=False).all()


def _finalize_metadata_outputs(
    cache_file: str,
    output_file: str,
    error_output_file: str,
    expected_files: set[str],
    test_case_urls: set[str],
    lock_path: str | None = None,
    delete_tmp: bool = True,
    delete_lock: bool = True,
    retain_failed_cache: bool = True,
) -> bool:
    context = file_lock(lock_path) if lock_path else nullcontext()
    with context:
        cache_df = _read_metadata_cache(cache_file)
        missing_files = expected_files - _tried_metadata_files(cache_df)
        if missing_files:
            logging.info(
                "Skipping method-metadata merge for %s; %s files have not been tried",
                Path(output_file).stem,
                len(missing_files),
            )
            return False

        failed_files = _failed_metadata_files(cache_df)
        error_rows = cache_df[
            cache_df[METHOD_METADATA_FILE_COLUMN].isin(failed_files)
        ].copy()
        output_df = cache_df[cache_df[METHOD_METADATA_FLAG_COLUMN].isna()].copy()
        output_df["frameworks"] = output_df["frameworks"].fillna("")
        output_df.loc[~output_df["url"].isin(test_case_urls), "frameworks"] = ""
        _write_dataframe_csv(output_file, output_df, METHOD_METADATA_COLUMNS, [])

        if not error_rows.empty:
            _write_dataframe_csv(
                error_output_file,
                error_rows,
                METHOD_METADATA_CACHE_COLUMNS,
                [],
            )
        elif os.path.exists(error_output_file):
            os.remove(error_output_file)

        if delete_tmp and (not failed_files or not retain_failed_cache):
            remove_file_if_exists(cache_file)
            remove_file_if_exists(f"{cache_file}.tmp")
            remove_file_if_exists(f"{output_file}.tmp")
            remove_file_if_exists(f"{error_output_file}.tmp")
    if delete_lock and lock_path:
        remove_file_if_exists(lock_path)
    return True


def _build_metadata_scanner(
    MethodMetadataScannerImpl,
    repository_name: str,
    repository_root: str,
    repository_url: str,
    commit_hash: str,
):
    started_at = time.monotonic()
    scanner = MethodMetadataScannerImpl.getInstance()
    scanner.init(
        repository_name,
        repository_root,
        repository_url,
        commit_hash,
        False,
    )
    _log_slow_operation(
        "method-metadata scanner-init finish thread=%s repository_root=%s commit=%s",
        time.monotonic() - started_at,
        threading.current_thread().name,
        repository_root,
        commit_hash,
    )
    return scanner


def _scan_metadata_in_file(
    scanner,
    repository_name: str,
    file: str,
    commit_hash: str,
) -> list[dict]:
    rows = []
    for metadata in scanner.scanMethodMetadata(file):
        rows.append(
            {
                "project": repository_name,
                "name": metadata.getName(),
                "url": metadata.getUrl(),
                "annotations": metadata.getAnnotations(),
                "annotations_fqn": metadata.getAnnotationsFqn(),
                "frameworks": metadata.getFrameworks(),
                "javadoc": metadata.getJavadoc(),
                METHOD_METADATA_FILE_COLUMN: file,
                METHOD_METADATA_HASH_COLUMN: commit_hash,
                METHOD_METADATA_FLAG_COLUMN: None,
                METHOD_METADATA_ERROR_COLUMN: None,
            }
        )
    return rows


def _scan_metadata_file_task(
    thread_local,
    MethodMetadataScannerImpl,
    repository_root: str,
    repository_name: str,
    repository_url: str,
    commit_hash: str,
    file: str,
    init_reset_interval_files: int,
) -> list[dict]:
    needs_reset = (
        init_reset_interval_files > 0
        and hasattr(thread_local, "scanner_file_count")
        and thread_local.scanner_file_count >= init_reset_interval_files
    )
    if needs_reset:
        del thread_local.scanner
        thread_local.scanner_file_count = 0
    if not hasattr(thread_local, "scanner"):
        thread_local.scanner = _build_metadata_scanner(
            MethodMetadataScannerImpl,
            repository_name,
            repository_root,
            repository_url,
            commit_hash,
        )
        thread_local.scanner_file_count = 0
    thread_local.scanner_file_count += 1

    started_at = time.monotonic()
    rows = _scan_metadata_in_file(
        thread_local.scanner,
        repository_name,
        file,
        commit_hash,
    )
    elapsed = time.monotonic() - started_at
    if elapsed >= SCAN_SLOW_SECONDS:
        logging.warning(
            "method-metadata slow-file project=%s file=%s rows=%s elapsed_seconds=%.1f",
            repository_name,
            file,
            len(rows),
            elapsed,
        )
    rows.append(_build_metadata_marker(repository_name, file, commit_hash))
    return rows


def scan_method_metadata(
    repository_df: DataFrame,
    repository_directory: str,
    data_directory: str,
    workspace_directory: str,
    replace: bool = False,
    shards: int = 1,
    shard: int = 1,
    merge_only: bool = False,
    merge_only_delete_empty: bool = False,
    merge_only_delete_tmp: bool = False,
    merge_only_delete_lock: bool = False,
    retry_errors: bool = True,
    merge_threshold: int = DEFAULT_SCAN_MERGE_THRESHOLD,
    merge_interval_seconds: int | None = None,
    max_workers: int = 1,
    init_reset_interval_files: int = 2000,
) -> list[str]:
    if merge_interval_seconds is None:
        merge_interval_seconds = METHOD_METADATA_FLUSH_INTERVAL_SECONDS
    MethodMetadataScannerImpl = None
    if not merge_only:
        from jpype import JClass
        MethodMetadataScannerImpl = JClass(
            "rnd.method.parser.call.graph.service.MethodMetadataScannerImpl"
        )

    output_files = []
    for _, repository in repository_df.iterrows():
        repository_name = util.require_project_name(repository)
        repository_url = repository["url"]
        commit_hash = repository["updated_hash"]
        repository_root = util.format_git_project_directory(
            repository_directory,
            repository_name,
        )
        output_file = util.format_method_metadata_file(data_directory, repository_name)
        method_file = util.format_method_list_file(data_directory, repository_name)
        if not os.path.exists(method_file):
            raise FileNotFoundError(
                f"method-metadata requires method input for {repository_name}: {method_file}"
            )
        try:
            method_df = pd.read_csv(method_file, usecols=["url", "artifact"], dtype=str)
        except ValueError as error:
            raise ValueError(
                f"method-metadata input must contain url and artifact columns: {method_file}"
            ) from error
        test_case_urls = set(
            method_df.loc[
                method_df["artifact"].map(is_test_case_method),
                "url",
            ].dropna().astype(str)
        )
        cache_dir = os.path.join(workspace_directory, ".method-metadata")
        cache_file = os.path.join(cache_dir, f"{repository_name}.csv")
        lock_path = os.path.join(cache_dir, f"{repository_name}.lock")
        error_dir = os.path.join(workspace_directory, ".method-metadata-error")
        error_output_file = os.path.join(error_dir, f"{repository_name}.csv")

        if replace:
            for existing_file in (output_file, cache_file, error_output_file):
                remove_file_if_exists(existing_file)
        elif (
            not merge_only
            and shards == 1
            and not os.path.exists(cache_file)
            and _is_metadata_output_current(output_file, commit_hash)
            and (not retry_errors or not os.path.exists(error_output_file))
        ):
            output_files.append(output_file)
            continue

        _log_scan_repository_start(
            "method-metadata",
            repository_name,
            commit_hash,
            shard,
            shards,
            max_workers,
            merge_threshold,
            merge_interval_seconds,
        )
        repository_started_at = time.monotonic()
        clone_and_checkout_commit(
            repository_url,
            repository_root,
            commit_hash,
        )
        java_files = sorted(collect_files(repository_root, "*.java"))
        relative_files = [
            file[len(repository_root) + 1:]
            for file in java_files
        ]
        expected_files = set(relative_files)

        if merge_only:
            merged = _finalize_metadata_outputs(
                cache_file,
                output_file,
                error_output_file,
                expected_files,
                test_case_urls,
                lock_path,
                merge_only_delete_tmp,
                merge_only_delete_lock,
                False,
            )
            if merged:
                output_files.append(output_file)
            if merged and merge_only_delete_empty:
                remove_empty_directory_tree(cache_dir)
                remove_empty_directory_tree(error_dir)
            continue

        os.makedirs(cache_dir, exist_ok=True)
        if not _metadata_cache_schema_current(cache_file):
            remove_file_if_exists(cache_file)
        cached_files = _load_cached_metadata_files(cache_file, retry_errors)
        files_to_scan = [
            file for file in relative_files
            if util.stable_shard_for_key(file, shards) == shard
            and file not in cached_files
        ]
        _log_scan_cache_filter(
            "method-metadata",
            repository_name,
            len(relative_files),
            len(cached_files),
            len(files_to_scan),
        )

        pending: list[dict] = []
        last_flush = time.monotonic()
        scan_started_at = time.monotonic()
        last_progress_at = scan_started_at
        last_progress_completed = 0
        completed_files = 0
        produced_rows = 0
        error_count = 0
        thread_local = threading.local()

        def collect_result(file: str) -> list[dict]:
            try:
                return _scan_metadata_file_task(
                    thread_local,
                    MethodMetadataScannerImpl,
                    repository_root,
                    repository_name,
                    repository_url,
                    commit_hash,
                    file,
                    init_reset_interval_files,
                )
            except Exception as error:
                logging.warning(
                    "method-metadata file exception project=%s file=%s",
                    repository_name,
                    file,
                    exc_info=True,
                )
                return [_build_metadata_error(repository_name, file, commit_hash, error)]

        if max_workers == 1:
            results = ((file, collect_result(file)) for file in files_to_scan)
            for file, rows in results:
                completed_files += 1
                produced_rows += len(rows)
                if any(
                    row.get(METHOD_METADATA_FLAG_COLUMN) == METHOD_METADATA_ERROR_MARKER
                    for row in rows
                ):
                    error_count += 1
                pending.extend(rows)
                last_progress_at, last_progress_completed = _maybe_log_scan_progress(
                    "method-metadata",
                    repository_name,
                    completed_files,
                    len(files_to_scan),
                    len(pending),
                    produced_rows,
                    error_count,
                    scan_started_at,
                    last_progress_at,
                    last_progress_completed,
                )
                if _should_flush_scan_cache(
                    len(pending),
                    last_flush,
                    merge_threshold,
                    merge_interval_seconds,
                ):
                    _flush_metadata_rows(cache_file, lock_path, pending, retry_errors)
                    last_flush = time.monotonic()
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(collect_result, file): file
                    for file in files_to_scan
                }
                for future in as_completed(futures):
                    rows = future.result()
                    completed_files += 1
                    produced_rows += len(rows)
                    if any(
                        row.get(METHOD_METADATA_FLAG_COLUMN) == METHOD_METADATA_ERROR_MARKER
                        for row in rows
                    ):
                        error_count += 1
                    pending.extend(rows)
                    last_progress_at, last_progress_completed = _maybe_log_scan_progress(
                        "method-metadata",
                        repository_name,
                        completed_files,
                        len(files_to_scan),
                        len(pending),
                        produced_rows,
                        error_count,
                        scan_started_at,
                        last_progress_at,
                        last_progress_completed,
                    )
                    if _should_flush_scan_cache(
                        len(pending),
                        last_flush,
                        merge_threshold,
                        merge_interval_seconds,
                    ):
                        _flush_metadata_rows(cache_file, lock_path, pending, retry_errors)
                        last_flush = time.monotonic()

        _flush_metadata_rows(cache_file, lock_path, pending, retry_errors)
        if shards == 1:
            if _finalize_metadata_outputs(
                cache_file,
                output_file,
                error_output_file,
                expected_files,
                test_case_urls,
                lock_path,
                retain_failed_cache=retry_errors,
            ):
                output_files.append(output_file)
        else:
            output_files.append(output_file)

        logging.info(
            "method-metadata finish project=%s completed_files=%s/%s produced_rows=%s errors=%s elapsed_seconds=%.1f",
            repository_name,
            completed_files,
            len(files_to_scan),
            produced_rows,
            error_count,
            time.monotonic() - repository_started_at,
        )

    return output_files
