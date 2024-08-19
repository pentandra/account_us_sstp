#!/usr/bin/env python
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import print_function

import csv
from collections import defaultdict
import datetime as dt
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
from itertools import batched

try:
    from progressbar import ETA, Bar, ProgressBar, SimpleProgress
except ImportError:
    ProgressBar = None

try:
    from proteus import Model, config
except ImportError:
    prog = os.path.basename(sys.argv[0])
    sys.exit("proteus must be installed to use %s" % prog)


def clean_boundaries(code):
    sys.stderr.write('Cleaning boundaries')
    sys.stderr.flush()
    Boundary = Model.get('account.tax.boundary')
    Boundary._proxy.delete(
        [c.id for c in Boundary.find([
            ('authority.subdivision.code', '=', code),
            ])], {})
    print('.', file=sys.stderr)

def clean_tax_rules(code):
    sys.stderr.write('Cleaning tax rules')
    sys.stderr.flush()
    TaxRule = Model.get('account.tax.rule')
    TaxRule._proxy.delete(
        [c.id for c in TaxRule.find([
            ('authority.subdivision.code', '=', code),
            ])], {})
    print('.', file=sys.stderr)

def clean_tax_codes(code):
    sys.stderr.write('Cleaning tax codes')
    sys.stderr.flush()
    TaxCode = Model.get('account.tax.code')
    TaxCode._proxy.delete(
        [c.id for c in TaxCode.find([('authority.subdivision.code', '=', code)])], {})
    print('.', file=sys.stderr)

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
        widgets = [
                SimpleProgress(),
                Bar(),
                ETA()]
        pbar = ProgressBar(widgets=widgets)
    else:
        pbar = iter
    return pbar(iterable)

def _remove_forbidden_chars(name):
    from trytond.tools import remove_forbidden_chars
    return remove_forbidden_chars(name)

def fetch(code):
    sys.stderr.write('Fetching')
    sys.stderr.flush()
    base = 'https://www.streamlinedsalestax.org/ratesandboundry/Boundary/'
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
    return {p.code_fips: p for p in Place.find([
        ('subdivision.code', '=', code)
        ])}

class TaxRuleCollector:

    def __init__(self, code, places):
        self.places = places
        self.rules = {}
        self.tax_sets = {}
        self.generic_taxes = {}

        self.Tax = Model.get('account.tax')
        self.TaxRule = Model.get('account.tax.rule')
        self.TaxRuleLine = Model.get('account.tax.rule')

    def get_rule(self, jurisdiction, authority):
        code_fips = jurisdiction.code_fips
        rule = self.rules.get(code_fips)
        if not rule:
            try:
                rule, = self.TaxRule.find([
                    ('authority', '=', authority),
                    ('jurisdiction.code_fips', '=', code_fips),
                    ])
            except ValueError:
                return
            self.rules[code_fips] = rule
        return rule

    def get_taxes(self, jurisdiction, authority):
        code_fips = jurisdiction.code_fips
        taxes = self.tax_sets.get(code_fips)
        if not taxes:
            try:
                taxes = self.Tax.find([
                    ('authority', '=', authority),
                    ('jurisdiction.code_fips', '=', code_fips),
                    ('type', '=', 'none'),
                    ('parent', '=', None),
                    ])
            except ValueError:
                return []
            self.tax_sets[code_fips] = taxes
        return taxes

    def get_generic_tax(self, tax):
        generic_tax = self.generic_taxes.get(tax.id)
        if not generic_tax:
            try:
                generic_tax, = self.Tax.find([
                    ('authority', '=', None),
                    ('group', '=', tax.group),
                    ('company', '=', tax.company),
                    ('type', '=', 'none'),
                    ('parent', '=', None),
                    ('childs', '=', None),
                    ('rate_type', '=', tax.rate_type),
                    ])
            except ValueError:
                sys.exit("Error could not find generic tax for %s" % tax.name)
            self.generic_taxes[tax.id] = generic_tax
        return generic_tax

    def collect(self, row):
        jurisdiction = self.places.get(row['fips_place_code'],
                self.places[row['fips_county_code']])
        authority = self.places[row['fips_state_code']]

        rule = self.get_rule(jurisdiction, authority)

        if not rule:
            name = '%s, %s Retail' % (jurisdiction.name,
                    jurisdiction.subdivision.code)
            rule = self.TaxRule(
                    name=name,
                    jurisdiction=jurisdiction,
                    authority=authority)

            for code_fips in ['fips_state_indicator', 'fips_county_code', 'fips_place_code']:
                if all(c == '0' for c in row[code_fips]):
                    continue

                place = self.places.get(row[code_fips])
                if place:
                    for tax in self.get_taxes(place, authority):
                        origin_tax = self.get_generic_tax(tax)

                        line = rule.lines.new()
                        line.group = tax.group
                        line.origin_tax = origin_tax
                        line.tax = tax
                        line.to_country = line.from_country = place.country
                        line.to_subdivision = place.subdivision
                        if tax.sourcing == 'intrastate':
                            line.from_subdivision = place.subdivision
                        else:
                            line.from_subdivision = None

                    for sd in batched(row['special_districts'], n=3):
                        pass

            rule.save()
        return rule

class TaxCodeCollector:

    def __init__(self, code, places):
        self.tax_codes = {}
        self.places = places

        authority = None
        try:
            authority, = [v for v in places.values() if v.parent == None]
        except:
            sys.exit("\nError could not find a state authority for the code: %s" % code)
        self.authority = authority

        with open(os.path.join(os.path.dirname(__file__),
                               'jurisdictions.csv'), newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=['code', 'code_tax', 'name'])
            self.names = {r['code_tax']: r['name'] for r in reader if r['code'] == code}

        TaxCode = Model.get('account.tax.code')
        root = TaxCode(name="%s Streamlined Sales Tax Report" % self.authority.subdivision.name,
                       code='SSTR-%s' % self.authority.subdivision.code,
                       authority=self.authority)
        root.save()

        taxable_sales = root.childs.new()
        taxable_sales.name = "Taxable Sales"
        taxable_sales.code = 'A'
        taxable_sales.authority = self.authority
        taxable_sales.save()

        total_sales = taxable_sales.childs.new()
        total_sales.name = "Total Sales"
        total_sales.code = '1'
        total_sales.authority = self.authority
        total_sales.save()

        exemptions = taxable_sales.childs.new()
        exemptions.name = "Exemptions and Deductions"
        exemptions.code = '2'
        exemptions.authority = self.authority
        exemptions.save()

        for name in ['Agriculture', 'Direct Pay', 'Government Exemption Organizations',
                     'Manufacturing', 'Resale', 'Other']:
            subcode = exemptions.childs.new()
            subcode.name = name
            subcode.authority = self.authority
            subcode.save()

        total_tax = root.childs.new()
        total_tax.name = "Total Tax Due"
        total_tax.code = 'B'
        total_tax.authority = self.authority
        total_tax.save()

        self.total_sales = total_sales
        self.total_tax = total_tax


    def get_tax_code(self, code_tax):
        tax_code = self.tax_codes.get(code_tax)
        if not tax_code:
            TaxCode = Model.get('account.tax.code')
            try:
                tax_code, = TaxCode.find([
                    ('authority', '=', self.authority),
                    ('code', '=', code_tax),
                    ])
            except ValueError:
                return
            self.tax_codes[code_tax] = tax_code
        return tax_code

    def collect(self, row):
        code_tax = row['composite_ser_code']
        if not code_tax or all(c == '0' for c in code_tax):
            return

        tax_code = self.get_tax_code(code_tax)
        if not tax_code:
            name = self.names.get(code_tax)
            if not name:
                print('Could not find jurisdiction name for %s' % code_tax)
                name = code_tax

            tax_code = self.total_tax.childs.new()
            tax_code.name = name
            tax_code.code = code_tax
            tax_code.authority = self.authority

            tax_code.save()
        return tax_code

def import_(code, boundaries):
    sys.stderr.write('Importing')
    sys.stderr.flush()
    Boundary = Model.get('account.tax.boundary')

    places = get_places(code)
    code_collector = TaxCodeCollector(code, places)
    rule_collector = TaxRuleCollector(code, places)

    _seen = defaultdict(set)
    def seen(rule, code=None):
        if code:
            if _seen.get(code) and rule in _seen[code]:
                return True
            _seen[code].add(rule)
            return False
        else:
            if _seen.get(rule):
                return True
            _seen[rule].add(1)
            return False

    _taxes = set()
    def setup_tax_lines(code, tax, amount='tax'):
        for op, type_ in zip(['+', '-'], ['invoice', 'credit']):
            line = code.lines.new()
            line.operator = op
            line.tax = tax
            line.amount = amount
            line.type = type_

    f = TextIOWrapper(BytesIO(boundaries), encoding='utf-8')
    reader = csv.DictReader(f, fieldnames=_fieldnames,
            restkey='special_districts')
    records = []
    for row in _progress(reader):
        authority = places[row['fips_state_code']]
        start_date = dt.datetime.strptime(row['start_date'], '%Y%m%d').date()
        end_date = dt.datetime.strptime(row['end_date'], '%Y%m%d').date()
        end_date = None if end_date == dt.date.max else end_date

        tax_code = code_collector.collect(row)
        rule = rule_collector.collect(row)

        if tax_code and not seen(rule, code=tax_code):
            for line in rule.lines:
                for tax in line.tax.childs:
                    taxes = [line.tax for line in tax_code.lines]
                    if tax not in taxes:
                        setup_tax_lines(tax_code, tax)
                        _taxes.add(tax)
            tax_code.save()
        elif not tax_code and not seen(rule):
            for line in rule.lines:
                for tax in line.tax.childs:
                    total_tax = code_collector.total_tax
                    taxes = [line.tax for line in total_tax.lines]
                    if not tax in taxes:
                        setup_tax_lines(total_tax, tax)
                        _taxes.add(tax)
            total_tax.save()


        records.append(Boundary(
                    type=row['record_type'],
                    start_date=start_date,
                    end_date=end_date,
                    authority=authority,
                    zipcode_low=row['zipcode_low'],
                    zipext_low=row['zipext_low'],
                    zipcode_high=row['zipcode_high'],
                    zipext_high=row['zipext_high'],
                    rule=rule,
                    code=tax_code,
                    ))

        if reader.line_num % 10000 == 0:
            Boundary.save(records)
            records = []

    Boundary.save(records)

    total_sales = code_collector.total_sales
    for tax in _taxes:
        # only the state-level bases are needed
        if tax.jurisdiction == code_collector.authority:
            setup_tax_lines(total_sales, tax, amount='base')
    total_sales.save()

    print('.', file=sys.stderr)

_fieldnames = ['record_type', 'start_date', 'end_date',
    'address_range_low', 'address_range_high', 'odd_even_indicator', 'street_predirectional',
    'street_name', 'street_suffix_abbr', 'street_post_directional', 'address_secondary_abbr',
    'address_secondary_low', 'address_secondary_high', 'address_secondary_odd_even',
    'city_name', 'zipcode', 'plus4', 'zipcode_low', 'zipext_low', 'zipcode_high', 'zipext_high',
    'composite_ser_code', 'fips_state_code', 'fips_state_indicator','fips_county_code',
    'fips_place_code', 'fips_place_class_code', 'longitude', 'latitude']

def main(database, codes, config_file=None):
    config.set_trytond(database, config_file=config_file)
    do_import(codes)


def do_import(codes):
    for code in codes:
        print(code, file=sys.stderr)
        code = code.upper()
        clean_boundaries('US-%s' % code)
        clean_tax_rules('US-%s' % code)
        clean_tax_codes('US-%s' % code)
        import_('US-%s' % code, fetch(code))


def run():
    parser = ArgumentParser()
    parser.add_argument('-d', '--database', dest='database', required=True)
    parser.add_argument('-c', '--config', dest='config_file',
        help='the trytond config file')
    parser.add_argument('codes', nargs='+')

    args = parser.parse_args()
    main(args.database, args.codes, args.config_file)


if __name__ == '__main__':
    run()
