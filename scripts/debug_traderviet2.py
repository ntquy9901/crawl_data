"""Debug traderviet.io HTML - analyze structItem structure."""
import re

with open(r'C:\Users\QUY\AppData\Local\Temp\traderviet_sample.html', encoding='utf-8') as f:
    content = f.read()

print(f'Total HTML size: {len(content)}')

# Check for Cloudflare challenge indicators
checks = [
    ('just a moment', 'just a moment' in content.lower()),
    ('attention', 'attention' in content.lower()[:5000]),
    ('cf-browser-verify', 'cf-browser-verify' in content),
    ('cloudflare', 'cloudflare' in content.lower()),
    ('__cf_chl', '__cf_chl' in content),
]
for name, found in checks:
    print(f'  {name}: {found}')

# Show first 2000 chars to see what's in the page
print('\n--- First 2000 chars ---')
print(content[:2000])
print('\n--- Last 1000 chars ---')
print(content[-1000:])

# Count how many structItem blocks
si_count = content.count('structItem--thread')
print(f'\nstructItem--thread count: {si_count}')

# Find all distinct href values
all_hrefs = re.findall(r'href="([^"]*)"', content)
print(f'\nTotal hrefs: {len(all_hrefs)}')
for u in all_hrefs[:50]:
    print(f'  href: {u}')
