#!/usr/bin/env python
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import print_function

import csv
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
#from itertools import batched

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
        ('subdivision.code', '=', 'US-%s' % code)
        ])}

def get_tax_codes(code):
    return {c.code_ser: c}

def import_boundaries(code, boundaries):
    sys.stderr.write('Importing boundaries')
    sys.stderr.flush()
    Boundary = Model.get('account.tax.boundary')
    Tax = Model.get('account.tax')
    TaxRule = Model.get('account.tax.rule')
    TaxRuleLine = Model.get('account.tax.rule')

    places = get_places(code)

    def get_rule(jurisdiction, authority):
        code_fips = jurisdiction.code_fips
        rule = rules.get(code_fips)
        if not rule:
            try:
                rule, = TaxRule.find([
                    ('jurisdiction.code_fips', '=', code_fips),
                    ])
            except ValueError:
                return
            rules[code_fips] = rule
        return rule
    rules = {}

    def get_taxes(jurisdiction, authority):
        code_fips = jurisdiction.code_fips
        taxes = tax_sets.get(code_fips)
        if not taxes:
            try:
                taxes = Tax.find([
                    ('jurisdiction.code_fips', '=', code_fips),
                    ('authority', '=', authority),
                    ('type', '=', 'none'),
                    ])
            except ValueError:
                return []
            tax_sets[code_fips] = taxes
        return taxes
    tax_sets = {}

    def get_generic_tax(tax):
        generic_tax = generic_taxes.get(tax.id)
        if not generic_tax:
            try:
                generic_tax, = Tax.find([
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
            generic_taxes[tax.id] = generic_tax
        return generic_tax
    generic_taxes = {}

    f = TextIOWrapper(BytesIO(boundaries), encoding='utf-8')
    reader = csv.DictReader(f, fieldnames=_fieldnames,
            restkey='special_districts')
    records = []
    for row in _progress(reader):
        jurisdiction = places.get(row['fips_place_code'],
                places[row['fips_county_code']])
        authority = places[row['fips_state_code']]
        start_date = dt.datetime.strptime(row['start_date'], '%Y%m%d').date()
        end_date = dt.datetime.strptime(row['end_date'], '%Y%m%d').date()
        end_date = None if end_date == dt.date.max else end_date

        if end_date != None:
            continue #TODO: for now only load current records

        rule = get_rule(jurisdiction, authority)
        if not rule:
            name = '%s, %s Retail' % (jurisdiction.name,
                    jurisdiction.subdivision.code)
            rule = TaxRule(
                    name=name,
                    jurisdiction=jurisdiction,
                    authority=authority)
            for code_fips in ['fips_state_indicator', 'fips_county_code', 'fips_place_code']:
                if all(c == '0' for c in row[code_fips]):
                    continue

                place = places.get(row[code_fips])
                if place:
                    taxes = get_taxes(place, authority)
                    for tax in taxes:
                        line = rule.lines.new()
                        line.start_date = start_date
                        line.end_date = end_date
                        line.group = tax.group
                        line.tax = tax
                        line.origin_tax = get_generic_tax(tax)
                        line.to_country = line.from_country = place.country
                        line.to_subdivision = place.subdivision
                        if tax.sourcing == 'intrastate':
                            line.from_subdivision = place.subdivision
                        else:
                            line.from_subdivision = None
            rule.save()

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
                    ))

        if reader.line_num % 10000 == 0:
            Boundary.save(records)
            records = []

        #for sd in batched(row['special_districts'], n=3):
        #    pass

    Boundary.save(records)
    print('.', file=sys.stderr)

def update_tax_codes(code):
    pass

def get_tax_rules(code):
    TaxRule = Model.get('account.tax.rule')
    return {(r.county_fips, r.place_fips): r for r in TaxRule.find([
        ('authority.subdivision.code', '=', 'US-%s' % code)
        ])}

def update_tax_rules(code):
    TaxRule = Model.get('account.tax.rule')

def update_tax_rules_interstate(codes):
    pass

_fieldnames = ['record_type', 'start_date', 'end_date',
    'address_range_low', 'address_range_high', 'odd_even_indicator', 'street_predirectional',
    'street_name', 'street_suffix_abbr', 'street_post_directional', 'address_secondary_abbr',
    'address_secondary_low', 'address_secondary_high', 'address_secondary_odd_even',
    'city_name', 'zipcode', 'plus4', 'zipcode_low', 'zipext_low', 'zipcode_high', 'zipext_high',
    'composite_ser_code', 'fips_state_code', 'fips_state_indicator','fips_county_code',
    'fips_place_code', 'fips_place_class_code', 'longitude', 'latitude']

#_fieldnames.extend([k + str(i) for i in range(1, 21) for k in [
#        'special_tax_district_code_source_',
#        'special_tax_district_code_',
#        'special_tax_district_authority_'
#        ]])

def main(database, codes, config_file=None):
    config.set_trytond(database, config_file=config_file)
    do_import(codes)


def do_import(codes):
    for code in codes:
        print(code, file=sys.stderr)
        code = code.upper()
        clean_boundaries('US-%s' % code)
        clean_tax_rules('US-%s' % code)
        #clean_tax_codes('US-%s' % code)
        boundaries = fetch(code)
        import_boundaries(code, boundaries)


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
