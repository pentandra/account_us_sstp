#!/usr/bin/env python
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import print_function

import csv
import datetime as dt
from decimal import Decimal
import os
import sys


try:
    from urllib.error import HTTPError
    from urllib.request import urlopen
    from urllib.parse import urljoin
except ImportError:
    from urllib2 import urlopen, HTTPError

from html.parser import HTMLParser
import zipfile
from argparse import ArgumentParser
from io import BytesIO, TextIOWrapper

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


def clean(code):
    sys.stderr.write('Cleaning')
    PostalCode = Model.get('country.postal_code')
    PostalCode._proxy.delete(
        [c.id for c in PostalCode.find([('country.code', '=', code)])], {})
    print('.', file=sys.stderr)

def _remove_forbidden_chars(name):
    from trytond.tools import remove_forbidden_chars
    return remove_forbidden_chars(name)

def fetch(code):
    sys.stderr.write('Fetching')
    base = 'https://www.streamlinedsalestax.org/ratesandboundry/Rates/'
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

def get_taxes(code):
    Tax = Model.get('account.tax')
    return {(t.name, t.start_date): t for t in Tax.find([
        ('authority', '!=', None),
        ('authority.subdivision.code', '=', code),
        ])}

def get_places(code):
    Place = Model.get('census.place')
    return {p.code_fips: p for p in Place.find([('subdivision.code', '=', 'US-%s' % code)])}

def get_groups():
    TaxGroup = Model.get('account.tax.group')
    return {g.code: g for g in TaxGroup.find([])}

def get_company():
    Company = Model.get('company.company')
    company, = Company.find()
    return company

def get_tax_account(company=None):
    Account = Model.get('account.account')

    if not company:
        company = get_company()

    return Account.find([
        ('company', '=', company.id),
        ('name', '=', 'Main Tax'),
        ], limit=1)

def update_taxes(code, taxes):
    TaxRule = Model.get('account.tax.rule')
    Tax = Model.get('account.tax')
    print('Importing', file=sys.stderr)

    places = get_places(code)
    groups = get_groups()
    tax_account, = get_tax_account()

    f = TextIOWrapper(BytesIO(fetch(code)), encoding='utf-8')
    records = []
    current_code_fips = None
    for row in _progress(list(csv.DictReader(f, fieldnames=_fieldnames))):
        authority = places[row['state']]
        code_fips = row['jurisdiction_fips_code']
        jurisdiction = places.get(row['jurisdiction_fips_code'])
        start_date = dt.datetime.strptime(row['start_date'], '%Y%m%d').date()
        end_date = dt.datetime.strptime(row['end_date'], '%Y%m%d').date()

        for type_ in ['general_rate_intrastate', 'general_rate_interstate',
            'food_rate_intrastate', 'food_rate_interstate']:
            name = '%s %s' % (code_fips, type_)
            description = '%s tax (%s)' % (code_fips
                    if jurisdiction is None else jurisdiction.name, row[type_])

            if current_code_fips != code_fips:
                if (name, None) in taxes:
                    parent = taxes[(name, None)]
                else:
                    parent = Tax(name=name)

                parent.jurisdiction=jurisdiction
                parent.description = description
                parent.authority = authority
                parent.type = 'none'
                parent.group = groups[row['jurisdiction_type']]
                records.append(parent)


            if (name, start_date) in taxes:
                record = taxes[(name, start_date)]
            else:
                record = Tax(name=name)

            record.jurisdiction=jurisdiction
            record.description = description
            record.authority = authority
            record.type = 'percentage'
            record.group = groups[row['jurisdiction_type']]
            record.rate = Decimal(row[type_])
            record.start_date = start_date
            record.end_date = None if end_date == dt.date.max else end_date

            record.invoice_account = tax_account
            record.credit_note_account = tax_account

            records.append(record)
        current_code_fips = code_fips

    Tax.save(records)
    return {(r.name, r.start_date): r for r in records}

def update_taxes_parent(taxes):
    print("Update taxes parent", file=sys.stderr)
    Tax = Model.get('account.tax')

    records = []
    for k, record in _progress(taxes.items()):
        name, start_date = k
        if record.type == 'none':
            continue
        else:
            record.parent = taxes[(name, None)]
            records.append(record)
    Tax.save(records)

_fieldnames = ['state', 'jurisdiction_type', 'jurisdiction_fips_code',
    'general_rate_intrastate', 'general_rate_interstate',
    'food_rate_intrastate', 'food_rate_interstate', 'start_date', 'end_date']


def main(database, codes, config_file=None):
    config.set_trytond(database, config_file=config_file)
    do_import(codes)


def do_import(codes):
    for code in codes:
        print(code, file=sys.stderr)
        code = code.upper()
        taxes = get_taxes('US-%s' % code)
        taxes = update_taxes(code, taxes)
        update_taxes_parent(taxes)


def run():
    parser = ArgumentParser()
    parser.add_argument('-d', '--database', dest='database', required=True)
    parser.add_argument('-c', '--config', dest='config_file',
        help='the trytond config file')
    parser.add_argument('-a', '--active', action='store_true',
        help='only import active taxes')
    parser.add_argument('codes', nargs='+')

    args = parser.parse_args()
    main(args.database, args.codes, args.config_file)


if __name__ == '__main__':
    run()
