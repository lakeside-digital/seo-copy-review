"""Lakeside Digital SEO Copy Review. Python 3.10+, standard library only."""
import argparse
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
FIELDS = {'h1': 'H1 heading', 'title': 'Page title', 'meta': 'Meta description', 'intro': 'Introductory subheading',
          'body_h2': 'Body H2', 'body_h2_second': 'Second body H2', 'secondary_h1': 'Additional H1'}
NOW = lambda: datetime.now(timezone.utc).isoformat()


def read_rows(path):
    """Read a UTF-8 CSV or the first worksheet of an XLSX, without executing formulas."""
    path = Path(path)
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            rows = list(reader)
    elif path.suffix.lower() == '.xlsx':
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with zipfile.ZipFile(path) as archive:
            if sum(i.file_size for i in archive.infolist()) > 50_000_000:
                raise ValueError('Workbook is too large. Export the review sheet as a UTF-8 CSV.')
            strings = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
                strings = [''.join(t.text or '' for t in el.findall('.//s:t', ns)) for el in root]
            book = ET.fromstring(archive.read('xl/workbook.xml'))
            sheet = book.find('s:sheets', ns)[0]
            rid = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
            target = next(r.attrib['Target'] for r in rels if r.attrib['Id'] == rid)
            name = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            root = ET.fromstring(archive.read(name))
            grid = []
            for row in root.findall('s:sheetData/s:row', ns):
                cells = {}
                for cell in row.findall('s:c', ns):
                    if cell.find('s:f', ns) is not None:
                        raise ValueError('Input contains formulas. Paste values into a separate review sheet first.')
                    ref = cell.attrib.get('r', '')
                    match = re.match(r'([A-Z]+)[0-9]+$', ref)
                    if not match:
                        raise ValueError('Invalid workbook cell reference.')
                    col = 0
                    for char in match[1]:
                        col = col * 26 + ord(char) - 64
                    if col > 200:
                        raise ValueError('Too many columns. Use a dedicated review sheet.')
                    kind = cell.attrib.get('t')
                    value = cell.find('s:v', ns)
                    text = value.text if value is not None and value.text is not None else ''
                    if kind == 's':
                        text = strings[int(text)]
                    elif kind == 'inlineStr':
                        text = ''.join(t.text or '' for t in cell.findall('.//s:t', ns))
                    elif kind == 'e':
                        raise ValueError('Input contains an Excel error. Fix it before importing.')
                    cells[col - 1] = text
                if cells and any(cells.values()):
                    grid.append(cells)
            if not grid:
                raise ValueError('The first worksheet is empty.')
            width = max(grid[0]) + 1
            headers = [grid[0].get(i, '') for i in range(width)]
            rows = [{headers[i]: row.get(i, '') for i in range(width)} for row in grid[1:]]
    else:
        raise ValueError('Use an .xlsx file or UTF-8 .csv file.')
    if len(headers) != len(set(headers)) or any(not h for h in headers):
        raise ValueError('Column names must be non-empty and unique.')
    if not {'page_id', 'url'} <= set(headers):
        raise ValueError('Include page_id and url columns. See example.csv.')
    keys = []
    for key in FIELDS:
        pair = {'original_' + key, 'proposed_' + key}
        if pair & set(headers):
            if not pair <= set(headers):
                raise ValueError('Include both original_' + key + ' and proposed_' + key + '.')
            keys.append(key)
    if not keys:
        raise ValueError('Include at least one original/proposed copy field pair.')
    if not rows or len(rows) > 10000:
        raise ValueError('Provide between 1 and 10,000 page rows.')
    pages, seen = [], set()
    for number, row in enumerate(rows, 2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f'Row {number}: column count does not match the header.')
        pid = row['page_id'].strip()
        url = row['url'].strip()
        parsed = urlsplit(url)
        if not pid or pid in seen:
            raise ValueError(f'Row {number}: page_id must be non-empty and unique.')
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError(f'Row {number}: use an HTTP(S) page URL without embedded credentials.')
        seen.add(pid)
        fields = {}
        for key in keys:
            original, proposed = row['original_' + key], row['proposed_' + key]
            if max(len(original), len(proposed)) > 5000:
                raise ValueError(f'Row {number}: a copy field exceeds 5,000 characters.')
            # A blank/blank optional pair does not create a field that the page never had.
            if not original and not proposed:
                continue
            if key == 'intro' and not original:
                raise ValueError(f'Row {number}: new introductory subheadings are template changes. Review them separately.')
            fields[key] = {'label': FIELDS[key], 'original': original, 'proposed': proposed,
                           'applicable': True, 'required': key in ('h1', 'title', 'meta') or original != proposed,
                           'rationale': row.get('rationale', ''), 'condition': row.get('implementation_notes', '')}
        if not fields:
            raise ValueError(f'Row {number}: no copy to review.')
        pages.append({'id': pid, 'url': url, 'destination': url, 'type': row.get('page_type', 'Page'),
                      'locale': '', 'reviewable': True, 'fields': fields, 'issues': [],
                      'target': '', 'sourceRow': number, 'condition': row.get('implementation_notes', ''),
                      'inspection': 'Supplied spreadsheet; no live content inspection performed', 'httpStatus': ''})
    return pages


def make_baseline(input_path, brand_path):
    brand = json.loads(Path(brand_path).read_text(encoding='utf-8-sig'))
    if not isinstance(brand, dict) or not isinstance(brand.get('name'), str) or not brand['name'].strip():
        raise ValueError('brand.json needs a non-empty name.')
    for key in ('headerBackground', 'headerText', 'accent'):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', brand.get(key, '')):
            raise ValueError(f'{key} must be a six-digit hex colour.')
    for key in ('logo', 'image'):
        value = brand.get(key, '')
        if not isinstance(value, str) or (value and (Path(value).name != value or Path(value).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp', '.svg'))):
            raise ValueError(f'{key} must name an image file beside server.py, without folders.')
        if value and not (ROOT / value).is_file():
            raise ValueError(f'Missing {key} image: {value}')
    for key in ('caption', 'imageAlt', 'category'):
        if not isinstance(brand.get(key, ''), str):
            raise ValueError(f'{key} must be text.')
    if brand.get('font', 'Arial') not in ('Arial', 'Georgia', 'Verdana'):
        raise ValueError('Choose Arial, Georgia or Verdana for font.')
    pages = read_rows(input_path)
    content = {'pages': pages, 'brand': brand}
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
    return {**content, 'version': 'seo-copy-review-v1-' + digest, 'issueCounts': {},
            'scope': {'all': len(pages), 'unaffected': 0}}


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, directory, baseline):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'decisions.json'
        self.baseline = baseline
        self.pages = {p['id']: p for p in baseline['pages']}
        self.lock = threading.RLock()
        if self.path.exists():
            self.validate(self.read())

    def read(self):
        with self.lock:
            if self.path.exists():
                return json.loads(self.path.read_text(encoding='utf-8'))
            return {'baselineVersion': self.baseline['version'], 'revision': 0,
                    'currentId': self.baseline['pages'][0]['id'], 'pages': {}}

    def validate(self, state):
        if not isinstance(state, dict) or state.get('baselineVersion') != self.baseline['version']:
            raise ValueError('Spreadsheet or brand changed. Use a new --data-dir for a new review. Previous decisions remain intact.')
        if type(state.get('revision')) is not int or state['revision'] < 0:
            raise ValueError('Invalid revision.')
        if state.get('currentId') not in self.pages or not isinstance(state.get('pages'), dict):
            raise ValueError('Invalid page inventory in backup.')
        for pid, decision in state['pages'].items():
            if pid not in self.pages or not isinstance(decision, dict):
                raise ValueError('Unknown page in backup.')
            if not isinstance(decision.get('note', ''), str) or len(decision.get('note', '')) > 10000:
                raise ValueError('Invalid note.')
            if 'skipped' in decision and type(decision['skipped']) is not bool:
                raise ValueError('Invalid skipped flag.')
            if not isinstance(decision.get('fields', {}), dict):
                raise ValueError('Invalid field decisions.')
            for key, choice in decision.get('fields', {}).items():
                if key not in self.pages[pid]['fields'] or not isinstance(choice, dict):
                    raise ValueError('Unknown field in backup.')
                if choice.get('status') not in ('pending', 'proposed', 'original', 'edited'):
                    raise ValueError('Invalid decision.')
                if not isinstance(choice.get('edited', ''), str) or len(choice.get('edited', '')) > 5000:
                    raise ValueError('Invalid edited copy.')
                for flag in ('editedTouched', 'explicitPending'):
                    if flag in choice and type(choice[flag]) is not bool:
                        raise ValueError('Invalid draft flag.')
                if choice['status'] == 'edited' and not choice.get('edited', '').strip():
                    raise ValueError('Approve an empty value by keeping an explicitly empty original.')
                if choice['status'] == 'proposed' and not self.pages[pid]['fields'][key]['proposed'].strip():
                    raise ValueError('Cannot accept an empty proposal. Decide that field individually.')

    def write(self, state):
        self.validate(state)
        temp = self.path.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.path)

    def save(self, payload):
        with self.lock:
            state = self.read()
            if payload.get('baselineVersion') != self.baseline['version'] or payload.get('expectedRevision') != state['revision']:
                raise Conflict('Another tab or input version changed this review. Refresh before saving.')
            pid = payload.get('pageId')
            if pid not in self.pages:
                raise ValueError('Unknown page.')
            state['pages'][pid] = copy.deepcopy(payload.get('decision'))
            state['currentId'] = payload.get('currentId', pid)
            state['revision'] += 1
            state['updatedAt'] = NOW()
            self.write(state)
            return state

    def restore(self, payload):
        with self.lock:
            current = self.read()
            if payload.get('expectedRevision') != current['revision']:
                raise Conflict('Review changed. Refresh before restoring.')
            restored = copy.deepcopy(payload.get('backup'))
            self.validate(restored)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            (self.directory / f'before-import-{stamp}.json').write_text(json.dumps(current, ensure_ascii=False), encoding='utf-8')
            restored['revision'] = current['revision'] + 1
            restored['updatedAt'] = NOW()
            self.write(restored)
            return restored


def resolved(field, choice):
    return {'proposed': field['proposed'], 'original': field['original'], 'edited': choice.get('edited', '')}.get(choice.get('status', 'pending'), '')


def export_csv(baseline, state):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    # Prefix formula-like values for safe opening in spreadsheet software; backup keeps exact strings.
    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
    writer.writerow(['page_id', 'url', 'field', 'decision', 'original', 'proposed', 'edited_draft', 'approved_copy', 'page_note', 'skipped', 'implementation_notes'])
    for page in baseline['pages']:
        decision = state['pages'].get(page['id'], {})
        for key, field in page['fields'].items():
            choice = decision.get('fields', {}).get(key, {})
            writer.writerow(map(safe, [page['id'], page['url'], key, choice.get('status', 'pending'), field['original'], field['proposed'], choice.get('edited', ''), resolved(field, choice), decision.get('note', ''), decision.get('skipped', False), page['condition']]))
    return ('\ufeff' + out.getvalue()).encode('utf-8')


def handler(store):
    baseline = store.baseline
    class Handler(BaseHTTPRequestHandler):
        def allowed(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def send(self, status, body, kind='application/json; charset=utf-8', filename=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False)
            if isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.allowed():
                return self.send(403, {'error': 'Use the local review address.'})
            path = urlsplit(self.path).path
            if path == '/api/data':
                return self.send(200, {'baseline': baseline, 'state': store.read()})
            if path == '/api/backup':
                return self.send(200, store.read(), filename='seo-copy-review-backup.json')
            if path == '/api/export.csv':
                return self.send(200, export_csv(baseline, store.read()), 'text/csv; charset=utf-8', 'seo-copy-reviewed.csv')
            files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            for asset in ('logo', 'image'):
                name = baseline['brand'].get(asset)
                if name:
                    mime = {'.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}[Path(name).suffix.lower()]
                    files['/' + name] = (name, mime)
            if path not in files:
                return self.send(404, {'error': 'Not found'})
            name, kind = files[path]
            return self.send(200, (ROOT / name).read_bytes(), kind)

        def do_POST(self):
            if not self.allowed():
                return self.send(403, {'error': 'Use the local review address.'})
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers['Host']:
                return self.send(403, {'error': 'Use the local review window.'})
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return self.send(403, {'error': 'Cross-site request rejected.'})
            if not self.headers.get('Content-Type', '').startswith('application/json'):
                return self.send(415, {'error': 'JSON required.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 0 or length > 5_000_000:
                    raise ValueError('Request too large.')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError('Expected a JSON object.')
                path = urlsplit(self.path).path
                if path == '/api/save':
                    return self.send(200, store.save(payload))
                if path == '/api/restore':
                    return self.send(200, store.restore(payload))
                return self.send(404, {'error': 'Not found'})
            except Conflict as error:
                return self.send(409, {'error': str(error)})
            except (ValueError, TypeError, KeyError) as error:
                return self.send(400, {'error': str(error)})
            except OSError:
                return self.send(500, {'error': 'Disk save failed. Keep this window open and check folder permissions/storage.'})

        def log_message(self, fmt, *args):
            print(fmt % args, flush=True)
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default=str(ROOT / 'example.csv'), help='Prepared .xlsx (first worksheet) or UTF-8 .csv')
    parser.add_argument('--brand', default=str(ROOT / 'brand.json'))
    parser.add_argument('--data-dir', default=str(ROOT / 'private' / 'demo'))
    parser.add_argument('--port', type=int, default=8780)
    args = parser.parse_args()
    try:
        baseline = make_baseline(args.input, args.brand)
        store = Store(args.data_dir, baseline)
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(store))
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as error:
        parser.exit(1, f'Cannot start review: {error}\n')
    print(f'SEO Copy Review ready: http://127.0.0.1:{server.server_port}\n{len(baseline["pages"])} pages. Ctrl+C to stop. Decisions: {store.path}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
