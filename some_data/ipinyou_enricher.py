import sys
import argparse
import os

def get_ua_info(ua):
    # Если UA пустой или равен ClickHouse NULL, возвращаем Unknown
    if not ua or ua == '\\N':
        return 'Unknown', 'Unknown'

    ua_lower = ua.lower()

    # 1. Определяем платформу
    if 'android' in ua_lower:
        platform = 'Android'
    elif any(x in ua_lower for x in ['iphone', 'ipad', 'ipod']):
        platform = 'iPhone'
    elif 'windows nt' in ua_lower:
        platform = 'Windows'
    elif 'macintosh' in ua_lower or 'mac os x' in ua_lower:
        platform = 'Mac'
    elif 'linux' in ua_lower:
        platform = 'Linux'
    else:
        platform = 'Other'

    # 2. Определяем браузер
    if 'msie' in ua_lower or 'trident' in ua_lower:
        browser = 'IE'
    elif 'chrome' in ua_lower:
        browser = 'Chrome'
    elif 'firefox' in ua_lower:
        browser = 'Firefox'
    elif 'ucbrowser' in ua_lower:
        browser = 'UCBrowser'
    elif 'baiduboxapp' in ua_lower or 'bidubrowser' in ua_lower:
        browser = 'Baidu'
    elif 'safari' in ua_lower and 'chrome' not in ua_lower:
        browser = 'Safari'
    else:
        browser = 'Other'

    return platform, browser

def process_file(input_path, output_path, mode):
    # Индексы User-Agent согласно формату iPinYou
    # Bidding: index 3, Impression: index 4
    ua_index = 3 if mode == 'bidding' else 4
    
    print(f"Starting enrichment: {input_path} -> {output_path}")
    count = 0
    
    try:
        with open(input_path, 'r', encoding='utf-8', errors='replace') as f_in, \
             open(output_path, 'w', encoding='utf-8') as f_out:
            
            for line in f_in:
                row = line.rstrip('\n').split('\t')
                
                # Извлекаем UA и определяем данные
                ua = row[ua_index] if len(row) > ua_index else '\\N'
                platform, browser = get_ua_info(ua)
                
                # Добавляем новые колонки в конец списка
                row.append(platform)
                row.append(browser)
                
                # Записываем обратно в TSV
                f_out.write('\t'.join(row) + '\n')
                
                count += 1
                if count % 1000000 == 0:
                    print(f"Processed {count // 1000000}M rows...")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Done! Total processed: {count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="iPinYou Data Enricher (Platform & Browser)")
    parser.add_argument('--input', required=True, help='Path to normalized TSV file')
    parser.add_argument('--output', required=True, help='Path for enriched output file')
    parser.add_argument('--mode', choices=['bidding', 'impression'], required=True)
    
    args = parser.parse_args()
    process_file(args.input, args.output, args.mode)