import os
import sys

from html.parser import HTMLParser
import zipfile
from io import BytesIO, TextIOWrapper

try:
    from urllib.error import HTTPError
    from urllib.request import urlopen
    from urllib.parse import urljoin
except ImportError:
    from urllib2 import urlopen, HTTPError

try:
    from progressbar import ETA, Bar, ProgressBar, SimpleProgress
except ImportError:
    ProgressBar = None

try:
    from proteus import Model, config
except ImportError:
    prog = os.path.basename(sys.argv[0])
    sys.exit("proteus must be installed to use %s" % prog)

class LinksExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr in attrs:
                if attr[0] == 'href':
                    self.links.append(attr[1])

    def get_links(self):
        return self.links

def _progress(iterable):
    if ProgressBar:
        pbar = ProgressBar(
            widgets=[SimpleProgress(), Bar(), ETA()])
    else:
        pbar = iter
    return pbar(iterable)

def _remove_forbidden_chars(name):
    from trytond.tools import remove_forbidden_chars
    return remove_forbidden_chars(name)

def fetch(code, base):
    sys.stderr.write('Fetching')
    sys.stderr.flush()
    try:
        responce = urlopen(base)
    except HTTPError as e:
        sys.exit("\nError fetching directory listing: %s" % e.reason)
    parser = LinksExtractor()
    parser.feed(TextIOWrapper(responce, encoding='utf-8').read())
    parser.close()

    files = {os.path.basename(a)[:2]: urljoin(base, a) for a in parser.get_links()}

    try:
        responce = urlopen(files[code])
    except KeyError:
        sys.exit("\nFile not found for code: %s" % code)
    except HTTPError as e:
        sys.exit("\nError downloading %s: %s" % (code, e.reason))
    data = responce.read()

    root, ext = os.path.splitext(responce.url)
    if ext == '.zip':
        with zipfile.ZipFile(BytesIO(data)) as zf:
            data = zf.read(os.path.basename(root) + '.csv')
    print('.', file=sys.stderr)
    return data

def get_places(code):
    Place = Model.get('census.place')
    return {p.code_fips: p for p in Place.find([('subdivision.code', '=', code)])}

def get_company():
    Company = Model.get('company.company')
    company, = Company.find()
    return company

