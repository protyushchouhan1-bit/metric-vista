"""
Stage A & Stage B — Safe Ingestion, Immutable Archival, Header-Row Scanner,
Bottom Summary/Total Row Detector, and Parquet Conversion.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
import pandas as pd

MAX_FILE_BYTES = 15 * 1024 * 1024  # 15 MB MVP cap
MAX_ROWS = 100_000                 # 100,000 row MVP cap
MAX_ZIP_UNCOMPRESSED = 60 * 1024 * 1024  # Excel zip-bomb defense (60 MB)

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t=", "\r=")
TOTAL_ROW_PATTERN = re.compile(r"^\s*(grand\s+total|total|subtotal|summary|overall\s+total)\b", re.IGNORECASE)


def sanitize_csv_cell(value: Any) -> Any:
    """Neutralize CSV formula-injection payloads on export (=, +, -, @)."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        # Allow pure negative numbers like "-123.45"
        if value[0] == "-" and re.match(r"^-\d+(\.\d+)?$", value.strip()):
            return value
        return "'" + value
    return value


def sanitize_dataframe_for_csv_export(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of DataFrame with CSV formula injection neutralized."""
    out = df.copy()
    for col in out.select_dtypes(include=["object", "string"]).columns:
        out[col] = out[col].map(sanitize_csv_cell)
    return out


@dataclass
class IngestionResult:
    raw_path: str
    parquet_path: str
    file_hash_sha256: str
    sheet_names: List[str]
    selected_sheet: Optional[str]
    detected_header_row: int
    flagged_preamble_rows: List[str]
    flagged_total_rows: List[Dict[str, Any]]
    row_count: int
    column_count: int
    columns: List[str]
    warnings: List[str] = field(default_factory=list)


def _validate_excel_zip_safety(file_bytes: bytes) -> None:
    """Verify XLSX archive is valid and does not exceed zip-bomb decompression limits."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED:
                raise ValueError(
                    f"Excel archive uncompressed size ({total_uncompressed} bytes) exceeds safety limit."
                )
    except zipfile.BadZipFile as exc:
        raise ValueError("Uploaded .xlsx file failed magic-byte/ZIP integrity inspection.") from exc


def _detect_header_row_from_rows(preview_rows: List[List[Any]]) -> Tuple[int, List[str]]:
    """
    Inspect top 15 rows to locate the true header row and flag decorative title/logo rows.
    """
    best_idx = 0
    best_score = -1.0
    for idx, row in enumerate(preview_rows[:15]):
        non_empty = [c for c in row if c is not None and str(c).strip() != ""]
        if len(non_empty) < 2:
            continue
        str_cells = [c for c in non_empty if isinstance(c, str) and not re.match(r"^-?\d+(\.\d+)?$", c.strip())]
        unique_ratio = len(set(str(c).strip().lower() for c in non_empty)) / max(len(non_empty), 1)
        # Penalize rows that look like a single long title banner
        score = len(non_empty) * 1.5 + len(str_cells) * 1.0 + unique_ratio * 2.0
        if score > best_score:
            best_score = score
            best_idx = idx
    preamble = []
    for i in range(best_idx):
        text = " | ".join(str(c).strip() for c in preview_rows[i] if c is not None and str(c).strip() != "")
        if text:
            preamble.append(text)
    return best_idx, preamble


def _detect_and_strip_total_rows(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Inspect bottom 5 rows for 'Total' / 'Grand Total' summary rows so they are flagged
    for user review and never silently double-counted.
    """
    flagged: List[Dict[str, Any]] = []
    if df.empty:
        return df, flagged

    drop_indices: List[int] = []
    tail_indices = list(df.index[-5:])
    for idx in tail_indices:
        row_vals = [str(v).strip() for v in df.loc[idx].tolist() if pd.notna(v) and str(v).strip() != ""]
        if not row_vals:
            continue
        if any(TOTAL_ROW_PATTERN.match(val) for val in row_vals[:3]):
            drop_indices.append(idx)
            flagged.append({
                "row_index": int(idx),
                "preview": " | ".join(row_vals[:5]),
                "reason": "Detected bottom summary/Grand Total row; excluded to prevent double-counting.",
            })
    if drop_indices:
        df = df.drop(index=drop_indices).reset_index(drop=True)
    return df, flagged


def ingest_file(
    file_bytes: bytes,
    filename: str,
    org_id: str,
    dataset_id: str,
    storage_root: str,
    sheet_name: Optional[str] = None,
) -> IngestionResult:
    """
    Stage A + B ingestion:
    1. Enforce 15 MB & extension/magic-byte safety.
    2. Archive immutable raw file under /{org_id}/raw/.
    3. Scan top 15 rows for decorative preamble rows and bottom rows for Grand Totals.
    4. Enforce 100,000-row MVP cap and persist columnar Apache Parquet under /{org_id}/parquet/.
    """
    if not file_bytes:
        raise ValueError("Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise ValueError(f"File exceeds MVP 15 MB limit ({len(file_bytes)} bytes).")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".csv", ".xlsx", ".xls"}:
        raise ValueError(f"Unsupported file extension '{ext}'. Allowed: .csv, .xlsx, .xls.")

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    raw_dir = os.path.join(storage_root, org_id, "raw")
    parquet_dir = os.path.join(storage_root, org_id, "parquet")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(parquet_dir, exist_ok=True)

    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(filename))
    raw_path = os.path.join(raw_dir, f"{dataset_id}_{safe_name}")
    # Immutable archival: never overwrite existing raw archive
    if not os.path.exists(raw_path):
        with open(raw_path, "wb") as fh:
            fh.write(file_bytes)

    warnings: List[str] = []
    sheet_names: List[str] = []
    selected_sheet: Optional[str] = None
    header_row = 0
    preamble_rows: List[str] = []

    if ext == ".csv":
        # Auto-detect encoding cleanly
        decoded_text = None
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                decoded_text = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if decoded_text is None:
            raise ValueError("Unable to decode CSV file with supported encodings.")

        sample_lines = decoded_text.splitlines()[:15]
        preview_rows = [line.split(",") for line in sample_lines]
        header_row, preamble_rows = _detect_header_row_from_rows(preview_rows)
        df = pd.read_csv(io.StringIO(decoded_text), skiprows=header_row, low_memory=False)
    else:
        if ext == ".xlsx":
            _validate_excel_zip_safety(file_bytes)
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        sheet_names = list(wb.sheetnames)
        selected_sheet = sheet_name if sheet_name in sheet_names else sheet_names[0]
        ws = wb[selected_sheet]
        preview_rows = []
        for idx, row in enumerate(ws.iter_rows(values_only=True)):
            preview_rows.append(list(row))
            if idx >= 14:
                break
        header_row, preamble_rows = _detect_header_row_from_rows(preview_rows)
        wb.close()
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=selected_sheet, skiprows=header_row, engine="openpyxl")

    # Drop completely empty columns/rows
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    df.columns = [str(c).strip() for c in df.columns]

    if len(df) > MAX_ROWS:
        raise ValueError(f"Dataset has {len(df):,} rows, exceeding MVP cap of {MAX_ROWS:,} rows.")

    df, flagged_totals = _detect_and_strip_total_rows(df)
    if preamble_rows:
        warnings.append(f"Header-Row Scanner skipped {len(preamble_rows)} decorative title row(s) above headers.")
    if flagged_totals:
        warnings.append(f"Detected and excluded {len(flagged_totals)} bottom summary/Grand Total row(s).")

    # Coerce mixed object columns to clean strings for Parquet safety while keeping numeric/dates intact
    df_parquet = df.copy()
    for col in df_parquet.columns:
        if df_parquet[col].dtype == "object":
            df_parquet[col] = df_parquet[col].where(df_parquet[col].notna(), None).map(
                lambda x: str(x) if x is not None else None
            )

    parquet_path = os.path.join(parquet_dir, f"{dataset_id}.parquet")
    df_parquet.to_parquet(parquet_path, index=False, engine="pyarrow")

    return IngestionResult(
        raw_path=raw_path,
        parquet_path=parquet_path,
        file_hash_sha256=file_hash,
        sheet_names=sheet_names,
        selected_sheet=selected_sheet,
        detected_header_row=header_row,
        flagged_preamble_rows=preamble_rows,
        flagged_total_rows=flagged_totals,
        row_count=int(len(df_parquet)),
        column_count=int(len(df_parquet.columns)),
        columns=list(df_parquet.columns),
        warnings=warnings,
    )
