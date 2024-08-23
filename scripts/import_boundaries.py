#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import csv
from collections import defaultdict
from datetime import date
import os
import sys

from argparse import ArgumentParser
from io import BytesIO, TextIOWrapper
from itertools import batched, chain
from operator import itemgetter
from proteus import Model, config

from common import fetch, get_company, get_places, _progress


def clean_boundaries(code_subdivision):
    sys.stderr.write('Cleaning boundaries')
    sys.stderr.flush()
    company = get_company()
    Boundary = Model.get('account.tax.boundary')
    Boundary._proxy.delete([], {})
        #[c.id for c in Boundary.find([
        #    ('authority.subdivision.code', '=', code_subdivision),
        #    ])], {})
    print('.', file=sys.stderr)

def clean_tax_rules(code_subdivision):
    sys.stderr.write('Cleaning tax rules')
    sys.stderr.flush()
    company = get_company()
    TaxRule = Model.get('account.tax.rule')
    TaxRule._proxy.delete(
        [c.id for c in TaxRule.find([
            ('authority.subdivision.code', '=', code_subdivision),
            ('company', '=', company),
            ])], {})
    print('.', file=sys.stderr)

def clean_tax_codes(code_subdivision):
    sys.stderr.write('Cleaning tax codes')
    sys.stderr.flush()
    company = get_company()
    TaxCode = Model.get('account.tax.code')
    TaxCode._proxy.delete(
        [c.id for c in TaxCode.find([
            ('authority.subdivision.code', '=', code_subdivision),
            ('company', '=', company),
            ])], {})
    print('.', file=sys.stderr)

class TaxRuleCollector:

    def __init__(self, places, company=None):
        self.places = places
        self.rules = {}
        self.tax_sets = {}
        self.generic_taxes = {}
        self.company = company or get_company()

    def get_rule(self, name, authority):
        rule = self.rules.get(name)
        if not rule:
            TaxRule = Model.get('account.tax.rule')
            try:
                rule, = TaxRule.find([
                    ('authority', '=', authority),
                    ('company', '=', self.company),
                    ('name', '=', name),
                    ])
            except ValueError:
                return
            self.rules[name] = rule
        return rule

    def get_taxes(self, code, authority):
        taxes = self.tax_sets.get(code)
        if not taxes:
            Tax = Model.get('account.tax')
            try:
                taxes = Tax.find([
                    ('authority', '=', authority),
                    ('company', '=', self.company),
                    ('code', '=', code),
                    ('type', '=', 'none'),
                    ('parent', '=', None),
                    ])
            except ValueError:
                return []
            self.tax_sets[code] = taxes
        return taxes

    def get_generic_tax(self, tax):
        generic_tax = self.generic_taxes.get(tax.id)
        if not generic_tax:
            Tax = Model.get('account.tax')
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
            self.generic_taxes[tax.id] = generic_tax
        return generic_tax

    def collect(self, row):
        fips_codes = _fips_indices(row)
        special_codes = map(_special_code_index, batched(row['special_districts'], n=3))
        codes = tuple(filter(None, chain(fips_codes, special_codes)))
        name = '%s Retail' % '–'.join(codes)
        authority = self.places[row['fips_state_code']]

        rule = self.get_rule(name, authority)

        if not rule:
            TaxRule = Model.get('account.tax.rule')
            code_fips = next((c for c in reversed(fips_codes) if c), None)
            place = self.places.get(code_fips)

            rule = TaxRule(
                    name=name,
                    company=self.company,
                    place=place,
                    authority=authority)

            for code in codes:
                if all(c == '0' for c in code):
                    continue

                for tax in self.get_taxes(code, authority):
                    origin_tax = self.get_generic_tax(tax)

                    line = rule.lines.new()
                    line.group = tax.group
                    line.origin_tax = origin_tax
                    line.tax = tax
                    line.to_country = line.from_country = authority.country
                    line.to_subdivision = authority.subdivision
                    if tax.sourcing == 'intrastate':
                        line.from_subdivision = authority.subdivision
                    else:
                        line.from_subdivision = None

            rule.save()
        return rule

class TaxCodeCollector:

    def __init__(self, code_subdivision, places, company=None):
        self.tax_codes = {}
        self.places = places
        self.company = company or get_company()

        authority = None
        try:
            authority, = [v for v in places.values() if v.parent == None]
        except:
            sys.exit("\nError could not find a state authority for the code: %s" % code_subdivision)
        self.authority = authority

        with open(os.path.join(os.path.dirname(__file__),
                               'jurisdictions.csv'), newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=['code', 'code_tax', 'name'])
            self.names = {r['code_tax']: r['name'] for r in reader if r['code'] == code_subdivision}

        TaxCode = Model.get('account.tax.code')
        root = TaxCode(name="%s Streamlined Sales Tax Report" % self.authority.subdivision.name,
                       code='SSTR-%s' % self.authority.subdivision.code,
                       company=self.company,
                       authority=self.authority)
        root.save()

        taxable_sales = root.childs.new()
        taxable_sales.name = "Taxable Sales"
        taxable_sales.code = 'A'
        taxable_sales.authority = self.authority
        taxable_sales.company = self.company
        taxable_sales.save()

        total_sales = taxable_sales.childs.new()
        total_sales.name = "Total Sales"
        total_sales.code = '1'
        total_sales.authority = self.authority
        total_sales.company = self.company
        total_sales.save()

        exemptions = taxable_sales.childs.new()
        exemptions.name = "Exemptions and Deductions"
        exemptions.code = '2'
        exemptions.authority = self.authority
        exemptions.company = self.company
        exemptions.save()

        for name in ['Agriculture', 'Direct Pay', 'Government Exemption Organizations',
                     'Manufacturing', 'Resale', 'Other']:
            subcode = exemptions.childs.new()
            subcode.name = name
            subcode.authority = self.authority
            subcode.company = self.company
            subcode.save()

        total_tax = root.childs.new()
        total_tax.name = "Total Tax Due"
        total_tax.code = 'B'
        total_tax.authority = self.authority
        total_tax.company = self.company
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
                    ('company', '=', self.company),
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
            tax_code.company = self.company

            tax_code.save()
        return tax_code

def import_(code_subdivision, boundaries, from_date):
    sys.stderr.write('Importing boundaries active as of %s' % from_date.isoformat())
    sys.stderr.flush()
    Boundary = Model.get('account.tax.boundary')

    company = get_company()
    places = get_places(code_subdivision)
    code_collector = TaxCodeCollector(code_subdivision, places, company=company)
    rule_collector = TaxRuleCollector(places, company=company)

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
    def setup_tax_code_lines(code, tax, amount='tax'):
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
        start_date = date.fromisoformat(row['start_date'])
        end_date = date.fromisoformat(row['end_date'])
        end_date = None if end_date == date.max else end_date

        tax_code = code_collector.collect(row)
        rule = rule_collector.collect(row)

        if tax_code and not seen(rule, code=tax_code):
            for line in rule.lines:
                for tax in line.tax.childs:
                    taxes = [line.tax for line in tax_code.lines]
                    if tax not in taxes:
                        setup_tax_code_lines(tax_code, tax)
                        _taxes.add(tax)
            tax_code.save()
        elif not tax_code and not seen(rule):
            for line in rule.lines:
                for tax in line.tax.childs:
                    total_tax = code_collector.total_tax
                    taxes = [line.tax for line in total_tax.lines]
                    if not tax in taxes:
                        setup_tax_code_lines(total_tax, tax)
                        _taxes.add(tax)
            total_tax.save()


        if reader.line_num % 10000 == 0:
            Boundary.save(records)
            records = []

        if end_date and end_date <= from_date:
            continue

        records.append(Boundary(
                    type=row['record_type'],
                    start_date=start_date,
                    end_date=end_date,
                    authority=authority,
                    company=company,
                    zipcode_low=row['zipcode_low'],
                    zipext_low=row['zipext_low'],
                    zipcode_high=row['zipcode_high'],
                    zipext_high=row['zipext_high'],
                    rule=rule,
                    code=tax_code,
                    ))

    Boundary.save(records)

    total_sales = code_collector.total_sales
    for tax in _taxes:
        # only the state-level bases are needed
        if tax.place == code_collector.authority:
            setup_tax_code_lines(total_sales, tax, amount='base')
    total_sales.save()

    print('.', file=sys.stderr)

_fips_indices = itemgetter('fips_state_indicator', 'fips_county_code', 'fips_place_code')
_special_code_index = itemgetter(1)

_fieldnames = ['record_type', 'start_date', 'end_date',
    'address_range_low', 'address_range_high', 'odd_even_indicator', 'street_predirectional',
    'street_name', 'street_suffix_abbr', 'street_post_directional', 'address_secondary_abbr',
    'address_secondary_low', 'address_secondary_high', 'address_secondary_odd_even',
    'city_name', 'zipcode', 'plus4', 'zipcode_low', 'zipext_low', 'zipcode_high', 'zipext_high',
    'composite_ser_code', 'fips_state_code', 'fips_state_indicator','fips_county_code',
    'fips_place_code', 'fips_place_class_code', 'longitude', 'latitude']

_base = 'https://www.streamlinedsalestax.org/ratesandboundry/Boundary/'

def main(database, args, config_file=None):
    config.set_trytond(database, config_file=config_file)
    do_import(args)


def do_import(args):
    for code in args.codes:
        print(code, file=sys.stderr)
        code_subdivision = 'US-%s' % code.upper()
        from_date = date.min if args.all else args.from_date

        clean_boundaries(code_subdivision)
        clean_tax_codes(code_subdivision)
        import_(code_subdivision, fetch(code.upper(), _base), from_date)


def run():
    parser = ArgumentParser()
    parser.add_argument('-d', '--database', dest='database', required=True)
    parser.add_argument('-c', '--config', dest='config_file',
        help='the trytond config file')
    parser.add_argument('-f', '--from', dest='from_date',
        default=date.today().isoformat(), type=date.fromisoformat,
        help='import all boundary records active from the given date YYYY-MM-DD '
             '(defaults to %s)' % date.today().isoformat())
    parser.add_argument('--all', action='store_true',
        help='import all available boundary records (overrides --from)')
    parser.add_argument('codes', nargs='+')

    args = parser.parse_args()
    main(args.database, args, args.config_file)


if __name__ == '__main__':
    run()
