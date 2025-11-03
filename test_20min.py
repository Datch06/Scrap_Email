import re
import ssl
import urllib.request
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    def handle_data(self, data):
        self.text.append(data)
    def get_text(self):
        return ' '.join(self.text)

ID_NUMBER_PATTERN = re.compile(r'\bnum[eé]ro\s+d[\'\"]identification\s*:?\s*(\d[\d\s]{8,13})', re.IGNORECASE)

url = 'https://www.20minutes.fr/mentions'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

with opener.open(req, timeout=15) as resp:
    html = resp.read().decode('utf-8', errors='replace')

parser = TextExtractor()
parser.feed(html)
text = parser.get_text()

match = ID_NUMBER_PATTERN.search(text)
if match:
    id_number = match.group(1).replace(' ', '')
    print(f'✓ Trouvé: {id_number}')
    print(f'  Longueur: {len(id_number)} chiffres')
    if len(id_number) == 9:
        print(f'  Type: SIREN')
    elif len(id_number) == 14:
        print(f'  Type: SIRET')
else:
    print('✗ Non trouvé')
