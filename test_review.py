"""Disposable regression checks. Never reads or writes client decisions."""
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
import zipfile

from server import ROOT, Conflict, Store, export_csv, handler, make_baseline, read_rows


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.baseline = make_baseline(ROOT / 'example.csv', ROOT / 'brand.json')
        self.store = Store(self.directory / 'state', self.baseline)

    def tearDown(self):
        self.temp.cleanup()

    def save(self, fields, **kwargs):
        payload = {'baselineVersion': self.baseline['version'], 'expectedRevision': self.store.read()['revision'],
                   'pageId': 'HG001', 'currentId': 'HG001', 'decision': {'fields': fields, 'note': 'Test'}}
        payload.update(kwargs)
        return self.store.save(payload)

    def test_example_inventory_and_originals(self):
        self.assertEqual(3, len(self.baseline['pages']))
        self.assertEqual('Garden design', self.baseline['pages'][0]['fields']['h1']['original'])
        self.assertEqual({'h1', 'title', 'meta'}, set(self.baseline['pages'][0]['fields']))
        self.assertEqual(9, sum(len(p['fields']) for p in self.baseline['pages']))

    def test_persistence_and_stale_tabs(self):
        self.save({'h1': {'status': 'edited', 'edited': 'My deliberate edit', 'editedTouched': True}})
        resumed = Store(self.store.directory, self.baseline).read()
        self.assertEqual('My deliberate edit', resumed['pages']['HG001']['fields']['h1']['edited'])
        with self.assertRaises(Conflict):
            self.save({}, expectedRevision=0)
        self.assertEqual(1, self.store.read()['revision'])

    def test_backup_restore_and_validation(self):
        backup = self.save({'h1': {'status': 'original'}})
        self.save({'h1': {'status': 'proposed'}})
        restored = self.store.restore({'expectedRevision': 2, 'backup': backup})
        self.assertEqual('original', restored['pages']['HG001']['fields']['h1']['status'])
        self.assertEqual(3, restored['revision'])
        self.assertEqual(1, len(list(self.store.directory.glob('before-import-*.json'))))
        invalid = copy.deepcopy(backup)
        invalid['pages']['NOT-A-PAGE'] = {'fields': {}}
        with self.assertRaises(ValueError):
            self.store.restore({'expectedRevision': 3, 'backup': invalid})
        self.assertEqual(restored, self.store.read())

    def test_unknown_fields_and_invalid_types(self):
        for fields in ({'unknown': {'status': 'proposed'}}, {'h1': {'status': 'edited', 'edited': ''}},
                       {'h1': {'status': 'pending', 'editedTouched': 'true'}}, {'h1': {'status': 'approved'}}):
            with self.assertRaises(ValueError):
                self.save(fields)
        self.assertEqual({}, self.store.read()['pages'])

    def test_changed_input_does_not_reuse_approvals(self):
        self.save({'h1': {'status': 'proposed'}})
        changed = copy.deepcopy(self.baseline)
        changed['version'] += '-changed'
        with self.assertRaises(ValueError):
            Store(self.store.directory, changed)

    def test_pending_skip_and_exact_resolution(self):
        state = self.save({'h1': {'status': 'edited', 'edited': 'Reviewed heading'},
                           'title': {'status': 'original'},
                           'meta': {'status': 'pending', 'edited': 'Retained draft', 'editedTouched': True, 'explicitPending': True}})
        rows = list(csv.DictReader(io.StringIO(export_csv(self.baseline, state).decode('utf-8-sig'))))
        by_key = {(r['page_id'], r['field']): r for r in rows}
        self.assertEqual(9, len(rows))
        self.assertEqual('Reviewed heading', by_key['HG001', 'h1']['approved_copy'])
        self.assertEqual('Garden design | Harbour Gardens', by_key['HG001', 'title']['approved_copy'])
        self.assertEqual('', by_key['HG001', 'meta']['approved_copy'])
        self.assertEqual('Retained draft', by_key['HG001', 'meta']['edited_draft'])
        state = self.save({}, decision={'fields': {}, 'skipped': True, 'note': ''})
        self.assertTrue(state['pages']['HG001']['skipped'])
        self.assertEqual({}, state['pages']['HG001']['fields'])

    def test_csv_formula_safety_preserves_backup(self):
        state = self.save({'title': {'status': 'edited', 'edited': '=1+1'}})
        rows = list(csv.DictReader(io.StringIO(export_csv(self.baseline, state).decode('utf-8-sig'))))
        title = next(r for r in rows if r['page_id'] == 'HG001' and r['field'] == 'title')
        self.assertEqual("'=1+1", title['approved_copy'])
        self.assertEqual('=1+1', self.store.read()['pages']['HG001']['fields']['title']['edited'])

    def input_csv(self, text):
        path = self.directory / 'input.csv'
        path.write_text(text, encoding='utf-8')
        return path

    def test_input_ids_fields_and_duplicate_urls(self):
        prefix = 'page_id,url,original_title,proposed_title\n'
        rows = read_rows(self.input_csv(prefix + 'A,https://example.com/,Old,New\nB,https://example.com/,Old,New\n'))
        self.assertEqual(2, len(rows))
        self.assertEqual({'title'}, set(rows[0]['fields']))
        for text in (prefix + 'A,https://example.com/,Old,New\nA,https://example.com/,Old,New\n',
                     prefix + 'A,javascript:alert(1),Old,New\n',
                     'page_id,url,original_title\nA,https://example.com/,Old\n',
                     prefix + 'A,https://example.com/,Old,New,EXTRA\n'):
            with self.assertRaises(ValueError):
                read_rows(self.input_csv(text))

    def test_optional_fields_and_structure(self):
        text = 'page_id,url,original_h1,proposed_h1,original_body_h2,proposed_body_h2\nA,https://example.com/,Old,New,Details,Details\n'
        page = read_rows(self.input_csv(text))[0]
        self.assertTrue(page['fields']['h1']['required'])
        self.assertFalse(page['fields']['body_h2']['required'])
        text = 'page_id,url,original_intro,proposed_intro\nA,https://example.com/,,New subheading\n'
        with self.assertRaises(ValueError):
            read_rows(self.input_csv(text))

    def test_brand_validation(self):
        brand = json.loads((ROOT / 'brand.json').read_text())
        for key, value in [('logo', '../private.png'), ('font', 'Bad; CSS'), ('accent', 'red')]:
            invalid = {**brand, key: value}
            path = self.directory / 'brand.json'
            path.write_text(json.dumps(invalid))
            with self.assertRaises(ValueError):
                make_baseline(ROOT / 'example.csv', path)

    def test_xlsx_reader_shared_strings_inline_and_formula_rejection(self):
        # Tiny synthetic Open XML fixture tests parsing; not a delivered workbook.
        def fixture(formula=False):
            path = self.directory / 'fixture.xlsx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Copy" sheetId="1" r:id="rId1"/></sheets></workbook>')
                archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="rId1" Target="/xl/worksheets/sheet1.xml"/></Relationships>')
                archive.writestr('xl/sharedStrings.xml', '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>page_id</t></si><si><t>url</t></si><si><t>original_title</t></si><si><t>proposed_title</t></si></sst>')
                formula_xml = '<f>1+1</f>' if formula else ''
                archive.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>PAGE1</t></is></c><c r="B2" t="inlineStr"><is><t>https://example.com/</t></is></c><c r="C2" t="inlineStr"><is><t>Original</t></is></c><c r="D2" t="inlineStr">' + formula_xml + '<is><t>Proposed &amp; verified</t></is></c></row></sheetData></worksheet>')
            return path
        self.assertEqual('Proposed & verified', read_rows(fixture())[0]['fields']['title']['proposed'])
        with self.assertRaisesRegex(ValueError, 'formulas'):
            read_rows(fixture(True))

    def test_http_save_export_and_private_file_isolation(self):
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.store))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{httpd.server_port}'
        def request(path, payload=None, **headers):
            body = json.dumps(payload).encode() if payload is not None else None
            if body:
                headers.setdefault('Content-Type', 'application/json')
            return urllib.request.urlopen(urllib.request.Request(url + path, data=body, headers=headers), timeout=5)
        try:
            self.assertEqual(3, len(json.load(request('/api/data'))['baseline']['pages']))
            payload = {'baselineVersion': self.baseline['version'], 'expectedRevision': 0, 'pageId': 'HG001', 'decision': {'fields': {'title': {'status': 'proposed'}}}}
            self.assertEqual(1, json.load(request('/api/save', payload))['revision'])
            self.assertIn(b'approved_copy', request('/api/export.csv').read())
            for path in ('/private/decisions.json', '/server.py', '/brand.json', '/../README.md'):
                with self.assertRaises(urllib.error.HTTPError) as context:
                    request(path)
                self.assertEqual(404, context.exception.code)
            with self.assertRaises(urllib.error.HTTPError) as context:
                request('/api/save', payload, Origin='https://example.com')
            self.assertEqual(403, context.exception.code)
            with self.assertRaises(urllib.error.HTTPError) as context:
                request('/api/data', Host='attacker.example')
            self.assertEqual(403, context.exception.code)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
