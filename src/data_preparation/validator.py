"""
validator.py

Validates and normalises raw TSV log files from the iPinYou RTB dataset
before loading them into ClickHouse.

The script accepts two log types and applies the following normalisation rules:
  - ad_exchange: empty or null values are replaced with 0 (Unknown category).
  - Numeric fields (widths, heights, prices, IDs): invalid or negative values
    are replaced with a NULL representation (empty string by default, or the
    ClickHouse NULL token \\N when --clickhouse is set).
  - ad_slot_visibility / ad_slot_format: values outside the allowed sets are
    mapped to 'Na'.
  - ad_slot_id: never modified.
  - Short rows are right-padded with empty strings; long rows have surplus
    tokens merged into the last field.

Parameters:
  --mode         Log type to process: 'bidding' or 'impression'.
  --input        Path to the raw input TSV file.
  --output       Path for the normalised output TSV file.
  --dry-run      Analyse only; do not write an output file.
  --report-size  Maximum number of sample issues to display (default: 20).
  --clickhouse   Represent NULL values as the ClickHouse NULL token (\\N).

Usage examples:
  python3 validator.py --mode bidding --input bid_log.tsv --dry-run
  python3 validator.py --mode bidding --input bid_log.tsv --output bid_log.ch.tsv --clickhouse
  python3 validator.py --mode impression --input imp_log.tsv --output imp_log.ch.tsv --clickhouse
"""

from typing import Dict, List, Optional, Tuple
import argparse
import os
import re
import sys

BIDDING_COLUMNS: List[str] = [
    'bid_id', 'timestamp', 'ipinyou_id', 'user_agent', 'ip',
    'region_id', 'city_id', 'ad_exchange', 'domain', 'url',
    'anonymous_url', 'ad_slot_id', 'ad_slot_width', 'ad_slot_height',
    'ad_slot_visibility', 'ad_slot_format', 'ad_slot_floor_price',
    'creative_id', 'bidding_price', 'advertiser_id', 'user_profile_ids',
]

IMPRESSION_COLUMNS: List[str] = [
    'bid_id', 'timestamp', 'log_type', 'ipinyou_id', 'user_agent', 'ip',
    'region_id', 'city_id', 'ad_exchange', 'domain', 'url',
    'anonymous_url', 'ad_slot_id', 'ad_slot_width', 'ad_slot_height',
    'ad_slot_visibility', 'ad_slot_format', 'ad_slot_floor_price',
    'creative_id', 'bidding_price', 'paying_price', 'landing_page_url',
    'advertiser_id', 'user_profile_ids',
]

ALLOWED_VISIBILITY: set = {
    'FirstView', 'SecondView', 'ThirdView', 'FourthView', 'FifthView',
    'SixthView', 'SeventhView', 'EighthView', 'NinthView', 'TenthView',
    'Na', 'OtherView',
}

ALLOWED_FORMAT: set = {'Fixed', 'Pop', 'Na', 'OtherView', 'Other'}

NUMERIC_COLS: set = {
    'ad_slot_width', 'ad_slot_height', 'ad_slot_floor_price',
    'bidding_price', 'paying_price', 'region_id', 'city_id',
    'advertiser_id', 'log_type',
}


def is_nullish(s: Optional[str]) -> bool:
    if s is None:
        return True
    s2 = s.strip()
    return s2 == '' or s2.lower() == 'null'


def to_uint_or_none(s: str) -> Optional[int]:
    if is_nullish(s):
        return None
    try:
        v = int(s)
        return v if v >= 0 else None
    except ValueError:
        m = re.search(r'\d+', s)
        if m:
            try:
                return int(m.group(0))
            except ValueError:
                return None
        return None


def to_uint8_or_zero(s: str) -> int:
    if is_nullish(s):
        return 0
    m = re.search(r'(\d+)', s)
    if not m:
        return 0
    try:
        return int(m.group(1)) % 256
    except ValueError:
        return 0


def null_token(clickhouse: bool) -> str:
    return r'\N' if clickhouse else ''


def normalize_field(col_name: str, val: str, clickhouse: bool) -> Tuple[str, Optional[str]]:
    if is_nullish(val):
        if col_name == 'ad_exchange':
            return '0', 'ad_exchange empty -> 0'
        return null_token(clickhouse), None

    if col_name == 'ad_exchange':
        v = to_uint8_or_zero(val)
        if str(v) != val:
            return str(v), f"ad_exchange normalised from '{val}' to '{v}'"
        return str(v), None

    if col_name == 'ad_slot_id':
        return val, None

    if col_name in NUMERIC_COLS:
        iv = to_uint_or_none(val)
        if iv is None:
            nt = null_token(clickhouse)
            return nt, f"{col_name} invalid -> set to {repr(nt)}"
        if str(iv) != val:
            return str(iv), f"{col_name} normalised from '{val}' to '{iv}'"
        return str(iv), None

    if col_name == 'ad_slot_visibility':
        v = val.strip()
        if v in ALLOWED_VISIBILITY:
            return v, None
        v_cap = v[0].upper() + v[1:] if v else v
        if v_cap in ALLOWED_VISIBILITY:
            return v_cap, f"visibility fixed '{val}' -> '{v_cap}'"
        return 'Na', f"visibility '{val}' unknown -> 'Na'"

    if col_name == 'ad_slot_format':
        v = val.strip()
        if v in ALLOWED_FORMAT:
            return v, None
        return 'Na', f"format '{val}' unknown -> 'Na'"

    return val, None


def build_row(tokens: List[str], expected_cols: List[str]) -> List[str]:
    n = len(expected_cols)
    if len(tokens) < n:
        tokens += [''] * (n - len(tokens))
    if len(tokens) > n:
        extras = tokens[n - 1:]
        tokens = tokens[:n - 1] + ['\t'.join(extras)]
    return tokens[:n]


def validate_file(
    path: str,
    mode: str,
    dry_run: bool,
    output: Optional[str],
    report_size: int,
    clickhouse: bool,
) -> Dict:
    expected = BIDDING_COLUMNS if mode == 'bidding' else IMPRESSION_COLUMNS

    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")
    if not dry_run and not output:
        raise ValueError("--output is required when not running in --dry-run mode")

    total = 0
    changed = 0
    samples: List[Tuple[int, str, List[str]]] = []
    fix_counters: Dict[str, int] = {}
    col_counters: Dict[str, int] = {}
    field_change_count = 0
    null_field_changes = 0

    out_f = None
    if not dry_run:
        out_f = open(output, 'w', encoding='utf-8')

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                total += 1
                orig = line.rstrip('\n')
                toks = orig.split('\t')
                row = build_row(toks, expected)

                notes: List[str] = []
                norm: List[str] = []
                for col, val in zip(expected, row):
                    nval, note = normalize_field(col, val, clickhouse)
                    norm.append(nval)
                    if note:
                        notes.append(note)
                        fix_counters[note] = fix_counters.get(note, 0) + 1
                        col_counters[col] = col_counters.get(col, 0) + 1
                        field_change_count += 1
                        if nval == null_token(clickhouse):
                            null_field_changes += 1

                if notes:
                    changed += 1
                    if len(samples) < report_size:
                        samples.append((total, orig, notes))

                if out_f is not None:
                    out_f.write('\t'.join(norm) + '\n')
    finally:
        if out_f is not None:
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
    print(f"rows with changes: {res['changed']}")

    fix_counters = res.get('fix_counters', {})
    col_counters = res.get('col_counters', {})
    field_change_count = res.get('field_change_count', 0)
    null_field_changes = res.get('null_field_changes', 0)

    if fix_counters:
        print('\nFix statistics (note -> count, % of changed fields):')
        for note, cnt in sorted(fix_counters.items(), key=lambda x: -x[1]):
            pct = cnt / field_change_count * 100 if field_change_count else 0.0
            print(f'  {note}: {cnt} ({pct:.2f}%)')

    if col_counters:
        print('\nChanges by column:')
        for col, cnt in sorted(col_counters.items(), key=lambda x: -x[1]):
            pct = cnt / field_change_count * 100 if field_change_count else 0.0
            print(f'  {col}: {cnt} ({pct:.2f}%)')

    print(f'\nTotal fields changed: {field_change_count}')
    if clickhouse:
        print(f"Fields set to \\N: {null_field_changes}")

    samples = res.get('samples', [])
    if samples:
        print(f'\nSample issues (first {len(samples)}):')
        for idx, orig, notes in samples:
            print('---')
            print(f'line #{idx}:')
            print(orig)
            print('notes:')
            for n in notes:
                print('  -', n)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description='Validate and normalise iPinYou TSV log files.',
    )
    parser.add_argument('--mode', choices=['bidding', 'impression'], required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--report-size', type=int, default=20)
    parser.add_argument('--clickhouse', action='store_true')
    args = parser.parse_args(argv)

    res = validate_file(
        path=args.input,
        mode=args.mode,
        dry_run=args.dry_run,
        output=args.output,
        report_size=args.report_size,
        clickhouse=args.clickhouse,
    )
    print_stats(res, args.clickhouse)

    if not args.dry_run and args.output:
        print(f'\nNormalised output written to: {args.output}')
        if args.clickhouse:
            print('ClickHouse mode: NULLs represented as \\N')


if __name__ == '__main__':
    main()
