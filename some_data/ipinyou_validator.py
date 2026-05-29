"""
ipinyou_validator_v3.py

Enhanced iPinYou validator (v3)
- Keeps behavior from v2 (don't change ad_slot_id, accept OtherView, optional --clickhouse \\N nulls)
- Adds detailed statistics:
  - counts per fix-note (e.g. "ad_exchange empty -> 0")
  - counts per column (how many fields in each column were changed)
  - total fields changed and how many were set to ClickHouse NULL token (if --clickhouse)
  - percentage breakdowns

Usage examples:
  python3 ipinyou_validator_v3.py --mode bidding --input bid_log --dry-run --report-size 20
  python3 ipinyou_validator_v3.py --mode bidding --input bid_log --output bid_log.ch.tsv --clickhouse
"""
from typing import List, Tuple, Optional, Dict
import argparse
import sys
import os
import re

# Columns for each mode (do not change order)
BIDDING_COLUMNS = [
    'bid_id','timestamp','ipinyou_id','user_agent','ip','region_id','city_id','ad_exchange',
    'domain','url','anonymous_url','ad_slot_id','ad_slot_width','ad_slot_height','ad_slot_visibility',
    'ad_slot_format','ad_slot_floor_price','creative_id','bidding_price','advertiser_id','user_profile_ids'
]

IMPRESSION_COLUMNS = [
    'bid_id','timestamp','log_type','ipinyou_id','user_agent','ip','region_id','city_id','ad_exchange',
    'domain','url','anonymous_url','ad_slot_id','ad_slot_width','ad_slot_height','ad_slot_visibility',
    'ad_slot_format','ad_slot_floor_price','creative_id','bidding_price','paying_price','landing_page_url','advertiser_id','user_profile_ids'
]

ALLOWED_VISIBILITY = set(['FirstView','SecondView','ThirdView','FourthView','FifthView','SixthView','SeventhView','EighthView','NinthView','TenthView','Na','OtherView'])
ALLOWED_FORMAT = set(['Fixed','Pop','Na','OtherView','Other'])

# Helpers

def is_nullish(s: Optional[str]) -> bool:
    if s is None:
        return True
    s2 = s.strip()
    return s2 == '' or s2.lower() == 'null'


def to_uint8_or_zero(s: str) -> int:
    if is_nullish(s):
        return 0
    m = re.search(r"(\d+)", s)
    if not m:
        return 0
    try:
        v = int(m.group(1))
    except Exception:
        return 0
    if v < 0:
        return 0
    return v % 256


def to_int_or_none(s: str) -> Optional[int]:
    if is_nullish(s):
        return None
    try:
        return int(s)
    except Exception:
        m = re.search(r"-?\d+", s)
        if m:
            try:
                return int(m.group(0))
            except Exception:
                return None
        return None


def null_repr(clickhouse: bool) -> str:
    return '\\N' if clickhouse else ''


def normalize_field(col_name: str, val: str, clickhouse: bool) -> Tuple[str, Optional[str]]:
    """Normalize a single field. Return (normalized_value, note_or_None).
    Notes (same as v2):
    - ad_exchange -> integer (0 default)
    - ad_slot_id -> left unchanged
    - numeric fields -> coerced to int where possible, else NULL representation ('' or '\\N')
    - visibility/format -> mapped to allowed set, else 'Na'
    - literal 'null' and empty strings -> treated as NULL
    """
    if is_nullish(val):
        if col_name == 'ad_exchange':
            return '0', "ad_exchange empty -> 0"
        return null_repr(clickhouse), None

    if col_name == 'ad_exchange':
        v = to_uint8_or_zero(val)
        if str(v) != val:
            return str(v), f"ad_exchange normalized from '{val}' to '{v}'"
        return str(v), None

    # do NOT change ad_slot_id
    if col_name == 'ad_slot_id':
        return val, None

    numeric_cols = {'ad_slot_width','ad_slot_height','ad_slot_floor_price','bidding_price','paying_price','region_id','city_id','advertiser_id','log_type'}
    if col_name in numeric_cols:
        iv = to_int_or_none(val)
        if iv is None or iv < 0:
            return null_repr(clickhouse), f"{col_name} invalid or negative -> set to {repr(null_repr(clickhouse))}"
        if str(iv) != val:
            return str(iv), f"{col_name} normalized from '{val}' to '{iv}'"
        return str(iv), None

    if col_name == 'ad_slot_visibility':
        v = val.strip()
        if v not in ALLOWED_VISIBILITY:
            v_up = v[0].upper() + v[1:] if v else v
            if v_up in ALLOWED_VISIBILITY:
                return v_up, f"visibility fixed '{val}' -> '{v_up}'"
            else:
                return 'Na', f"visibility '{val}' unknown -> 'Na'"
        return v, None

    if col_name == 'ad_slot_format':
        v = val.strip()
        if v not in ALLOWED_FORMAT:
            return 'Na', f"format '{val}' unknown -> 'Na'"
        return v, None

    # default: keep as-is
    return val, None


def build_row(tokens: List[str], expected_cols: List[str]) -> List[str]:
    # pad or join extras into last field
    if len(tokens) < len(expected_cols):
        tokens += [''] * (len(expected_cols) - len(tokens))
    if len(tokens) > len(expected_cols):
        extras = tokens[len(expected_cols)-1:]
        tokens = tokens[:len(expected_cols)-1] + ['\t'.join(extras)]
    return tokens[:len(expected_cols)]


def validate_file(path: str, mode: str, dry_run: bool, output: Optional[str], report_size: int, clickhouse: bool) -> Dict:
    expected = BIDDING_COLUMNS if mode == 'bidding' else IMPRESSION_COLUMNS
    total = 0
    changed = 0
    samples = []

    # Detailed counters
    fix_counters: Dict[str, int] = {}
    col_counters: Dict[str, int] = {}
    field_change_count = 0
    null_field_changes = 0

    if not os.path.exists(path):
        raise FileNotFoundError(path)
    out_f = None
    if not dry_run:
        if not output:
            raise ValueError('output required when not dry-run')
        out_f = open(output, 'w', encoding='utf-8')

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            total += 1
            orig = line.rstrip('\n')
            toks = orig.split('\t')
            row = build_row(toks, expected)
            notes = []
            norm = []
            for col, val in zip(expected, row):
                nval, note = normalize_field(col, val, clickhouse)
                norm.append(nval)
                if note:
                    # record which fix and which column
                    notes.append(note)
                    fix_counters[note] = fix_counters.get(note, 0) + 1
                    col_counters[col] = col_counters.get(col, 0) + 1
                    field_change_count += 1
                    if nval == null_repr(clickhouse):
                        null_field_changes += 1
            if notes:
                changed += 1
                if len(samples) < report_size:
                    samples.append((total, orig, notes))
            if not dry_run:
                out_f.write('\t'.join(norm) + '\n')

    if out_f:
        out_f.close()

    return {
        'path': path,
        'mode': mode,
        'total': total,
        'changed': changed,
        'samples': samples,
        'fix_counters': fix_counters,
        'col_counters': col_counters,
        'field_change_count': field_change_count,
        'null_field_changes': null_field_changes,
    }


def print_stats(res: Dict, clickhouse: bool) -> None:
    print('--- Validation summary ---')
    print(f"file: {res['path']}")
    print(f"mode: {res['mode']}")
    print(f"total rows: {res['total']}")
    print(f"rows with changes/issues: {res['changed']}")

    fix_counters = res.get('fix_counters', {})
    col_counters = res.get('col_counters', {})
    field_change_count = res.get('field_change_count', 0)
    null_field_changes = res.get('null_field_changes', 0)

    if fix_counters:
        print('\nDetailed fix statistics (note -> count, percent of changed fields):')
        for note, cnt in sorted(fix_counters.items(), key=lambda x: -x[1]):
            pct = cnt / field_change_count * 100 if field_change_count else 0
            print(f"  {note}: {cnt} ({pct:.2f}%)")

    if col_counters:
        print('\nChanges by column (column -> changed field count, percent of changed fields):')
        for col, cnt in sorted(col_counters.items(), key=lambda x: -x[1]):
            pct = cnt / field_change_count * 100 if field_change_count else 0
            print(f"  {col}: {cnt} ({pct:.2f}%)")

    print(f"\nTotal fields changed: {field_change_count}")
    if clickhouse:
        print(f"Fields set to ClickHouse NULL token (\\N): {null_field_changes}")

    # Sample rows (if present)
    samples = res.get('samples', [])
    if samples:
        print('\nSample issues (first {0}):'.format(len(samples)))
        for idx, orig, notes in samples:
            print('---')
            print(f'line #{idx}:')
            print(orig)
            print('notes:')
            for n in notes:
                print('  -', n)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['bidding','impression'], required=True)
    p.add_argument('--input', required=True)
    p.add_argument('--output')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--report-size', type=int, default=20)
    p.add_argument('--clickhouse', action='store_true', help='Emit ClickHouse NULL token (\\N) for missing/unparsable values')
    args = p.parse_args(argv)

    res = validate_file(args.input, args.mode, args.dry_run, args.output, args.report_size, args.clickhouse)

    print_stats(res, args.clickhouse)

    if not args.dry_run and args.output:
        print(f"\nNormalized output written to: {args.output}")
        if args.clickhouse:
            print("ClickHouse-mode: NULLs represented as \\N")


if __name__ == '__main__':
    main()
