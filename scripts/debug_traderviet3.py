"""Debug traderviet.io - find actual thread URL structure."""
import re

import requests

url = 'https://traderviet.io/forums/phan-tich-chung-khoan-viet-nam.71/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}
r = requests.get(url, headers=headers, timeout=30)
html = r.text

# Check if it's a Cloudflare challenge
if '<title>Just a moment' in html or '__cf_chl_tk' in html:
    print("CLOUDFLARE CHALLENGE")
else:
    print("REAL CONTENT")

# Find structItem blocks with thread info
blocks = re.findall(
    r'<div class="structItem structItem--thread[^"]*"[^>]*>(.*?)</div>\s*</div>',
    html, re.DOTALL
)
print(f'structItem blocks: {len(blocks)}')

if len(blocks) == 0:
    blocks = re.findall(
        r'<div class="structItem[^"]*"[^>]*>(.*?)(?=<div class="structItem)',
        html, re.DOTALL
    )
    print(f'structItem blocks (alt): {len(blocks)}')

if len(blocks) == 0:
    blocks = re.findall(
        r'(structItem structItem--thread.*?)(?=structItem structItem--thread|</div>\s*</div>\s*</div>)',
        html, re.DOTALL
    )
    print(f'structItem blocks (alt2): {len(blocks)}')

# Show first block
if blocks:
    block = blocks[0]
    print(f'\nFirst block ({len(block)} chars):')
    print(block[:1500])

# Find all thread-like URLs
all_thread_hrefs = re.findall(r'href="(/threads/[^"]*)"', html)
print(f'\n/threads/ URLs: {len(all_thread_hrefs)}')
for u in all_thread_hrefs[:10]:
    print(f'  {u}')

# Find any post/thread URLs
all_links = re.findall(r'href="(/[^"]*)"', html)
thread_like = [u for u in all_links if any(x in u.lower() for x in ['thread', 'posts/', 'post-'])]
print(f'\nThread-like URLs: {len(thread_like)}')
for u in thread_like[:10]:
    print(f'  {u}')

# Find all links in the first structItem block
if blocks:
    block_links = re.findall(r'href="(/[^"]*)"', blocks[0])
    print('\nLinks in first structItem:')
    for u in block_links:
        print(f'  {u}')

# Look for the actual thread URL pattern in the page
sections = html.split('structItem structItem--thread')
print(f'\nSplit by structItem--thread: {len(sections)} pieces')
if len(sections) > 1:
    sec = sections[1][:2000]
    print('Section 1 preview:')
    print(sec)
