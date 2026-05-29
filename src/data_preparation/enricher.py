"""
enricher.py

Enriches normalised TSV log files from the iPinYou RTB dataset by appending
two derived columns to every row: platform and browser, inferred from the
User-Agent field.

Platform values: Android, iPhone, Windows, Mac, Linux, Other, Unknown.
Browser values:  IE, Chrome, Firefox, UCBrowser, Baidu, Safari, Other, Unknown.
'Unknown' is used when the User-Agent field is empty or equals the ClickHouse
NULL token (\\N).

Parameters:
  --input   Path to the normalised input TSV file.
  --output  Path for the enriched output TSV file.
  --mode    Log type: 'bidding' (User-Agent at column index 3) or
            'impression' (User-Agent at column index 4).

Usage examples:
  python3 enricher.py --mode bidding    --input bid_log.ch.tsv  --output bid_log.enriched.tsv
  python3 enricher.py --mode impression --input imp_log.ch.tsv  --output imp_log.enriched.tsv
"""

import argparse
import sys
from typing import Tuple


def get_ua_info(ua: str) -> Tuple[str, str]:
    if not ua or ua == r'\N':
        return 'Unknown', 'Unknown'

    ua_lower = ua.lower()

    if 'android' in ua_lower:
        platform = 'Android'
    elif any(token in ua_lower for token in ('iphone', 'ipad', 'ipod')):
        platform = 'iPhone'
    elif 'windows nt' in ua_lower:
        platform = 'Windows'
    elif 'macintosh' in ua_lower or 'mac os x' in ua_lower:
        platform = 'Mac'
    elif 'linux' in ua_lower:
        platform = 'Linux'
    else:
        platform = 'Other'

    if 'msie' in ua_lower or 'trident' in ua_lower:
        browser = 'IE'
    elif 'chrome' in ua_lower:
        browser = 'Chrome'
    elif 'firefox' in ua_lower:
        browser = 'Firefox'
    elif 'ucbrowser' in ua_lower:
        browser = 'UCBrowser'
    elif 'baiduboxapp' in ua_lower or 'baidubrowser' in ua_lower:
        browser = 'Baidu'
    elif 'safari' in ua_lower and 'chrome' not in ua_lower:
        browser = 'Safari'
    else:
        browser = 'Other'

    return platform, browser


def process_file(input_path: str, output_path: str, mode: str) -> None:
    ua_index = 3 if mode == 'bidding' else 4

    print(f'Starting enrichment: {input_path} -> {output_path}')
    count = 0

    try:
        with open(input_path, 'r', encoding='utf-8', errors='replace') as f_in, \
             open(output_path, 'w', encoding='utf-8') as f_out:

            for line in f_in:
                row = line.rstrip('\n').split('\t')

                ua = row[ua_index] if len(row) > ua_index else r'\N'
                platform, browser = get_ua_info(ua)

                row.append(platform)
                row.append(browser)

                f_out.write('\t'.join(row) + '\n')
                count += 1

                if count % 1_000_000 == 0:
                    print(f'Processed {count // 1_000_000}M rows...')

    except KeyboardInterrupt:
        print('\nInterrupted by user.')
        sys.exit(1)
    except OSError as exc:
        print(f'Error: {exc}')
        sys.exit(1)

    print(f'Done. Total rows processed: {count}')


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description='Enrich iPinYou TSV log files with platform and browser columns.',
    )
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', choices=['bidding', 'impression'], required=True)
    args = parser.parse_args(argv)
    process_file(args.input, args.output, args.mode)


if __name__ == '__main__':
    main()
