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
from itertools import batched, chain, groupby
from operator import attrgetter, itemgetter
from proteus import Model, config

from common import fetch, get_company, get_places, _progress


def clean_boundaries(code_subdivision, company=None):
    sys.stderr.write('Cleaning boundaries')
    sys.stderr.flush()

    if not company:
        company = get_company()

    Boundary = Model.get('account.tax.boundary')
    Boundary._proxy.delete([], {})
        #[c.id for c in Boundary.find([
        #    ('authority.subdivision.code', '=', code_subdivision),
        #    ])], {})
    print('.', file=sys.stderr)

def clean_tax_rules(code_subdivision, company=None):
    sys.stderr.write('Cleaning tax rules')
    sys.stderr.flush()

    if not company:
        company = get_company()

    TaxRule = Model.get('account.tax.rule')
    TaxRule._proxy.delete(
        [c.id for c in TaxRule.find([
            ('authority.subdivision.code', '=', code_subdivision),
            ('company', '=', company),
            ])], {})
    print('.', file=sys.stderr)

def clean_taxcodes(code_subdivision, company=None):
    sys.stderr.write('Cleaning tax codes')
    sys.stderr.flush()

    if not company:
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
        self.taxes = {}
        self.generic_taxes = {}
        self.company = company or get_company()

    def get_rule(self, name, authority, kind='sale'):
        rule = self.rules.get(name)
        if not rule:
            TaxRule = Model.get('account.tax.rule')
            try:
                rule, = TaxRule.find([
                    ('authority', '=', authority),
                    ('company', '=', self.company),
                    ('name', '=', name),
                    ('kind', '=', kind),
                    ])
            except ValueError:
                return
            self.rules[name] = rule
        return rule

    def get_taxes(self, code, authority):
        taxes = self.taxes.get(code)
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
            self.taxes[code] = taxes
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
                    ('product_class', '=', tax.product_class),
                    ])
            except ValueError:
                sys.exit("Error could not find generic tax for %s" % tax.name)
            self.generic_taxes[tax.id] = generic_tax
        return generic_tax

    def collect(self, row):
        authority = self.places[row['fips_state_code']]
        fips_codes = _fips_indices(row)
        special_codes = map(_special_code_index, batched(row['special_districts'], n=3))
        codes = tuple(filter(None, chain(fips_codes, special_codes)))
        name = '%s Retail' % '–'.join(codes)

        rule = self.get_rule(name, authority)

        if not rule:
            TaxRule = Model.get('account.tax.rule')
            code_fips = next((c for c in reversed(fips_codes) if c), None)
            place = self.places.get(code_fips)

            rule = TaxRule(
                    name=name,
                    kind='sale',
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
        self.taxcodes = {}
        self.places = places
        self.company = company or get_company()

        authority = None
        try:
            authority, = [v for v in places.values() if not v.parent]
        except:
            sys.exit("\nError could not find a state authority for the code: %s" % code_subdivision)
        self.authority = authority

        codenames = os.path.join(os.path.dirname(__file__), 'codenames.csv')
        if os.path.isfile(codenames):
            with open(codenames, newline='') as csvfile:
                reader = csv.DictReader(csvfile, fieldnames=['code', 'code_tax', 'name'])
                self.names = {r['code_tax']: r['name'] for r in reader if r['code'] == code_subdivision}

        TaxCode = Model.get('account.tax.code')
        root = TaxCode(name="%s Streamlined Sales Tax Report" % self.authority.subdivision.name,
                       code='%s–SSTR' % self.authority.subdivision.code,
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

        state_tax_due = total_tax.childs.new()
        state_tax_due.name = "State Tax Due"
        state_tax_due.code = '1'
        state_tax_due.authority = self.authority
        state_tax_due.company = self.company
        state_tax_due.save()

        jurisdiction_detail = total_tax.childs.new()
        jurisdiction_detail.name = "Jurisdiction Detail"
        jurisdiction_detail.code = '2'
        jurisdiction_detail.authority = self.authority
        jurisdiction_detail.company = self.company
        jurisdiction_detail.save()

        self.total_sales = total_sales
        self.state_tax_due = state_tax_due
        self.jurisdiction_detail = jurisdiction_detail


    def get_taxcode(self, code_tax):
        taxcode = self.taxcodes.get(code_tax)
        if not taxcode:
            TaxCode = Model.get('account.tax.code')
            try:
                taxcode, = TaxCode.find([
                    ('authority', '=', self.authority),
                    ('company', '=', self.company),
                    ('code', '=', code_tax),
                    ])
            except ValueError:
                return
            self.taxcodes[code_tax] = taxcode
        return taxcode

    def create_taxcode(self, code, name):
        if code == self.authority.code_fips:
            return self.state_tax_due

        taxcode = self.jurisdiction_detail.childs.new()
        taxcode.name = name
        taxcode.code = code
        taxcode.authority = self.authority
        taxcode.company = self.company
        taxcode.save()
        return taxcode

    @staticmethod
    def create_lines(code, tax, amount='tax'):
        for op, type_ in zip(['+', '-'], ['invoice', 'credit']):
            line = code.lines.new()
            line.operator = op
            line.tax = tax
            line.amount = amount
            line.type = type_

    def collect(self, row):
        code_tax = row['composite_ser_code']
        if not code_tax or all(c == '0' for c in code_tax):
            return

        taxcode = self.get_taxcode(code_tax)
        if not taxcode:
            name = self.names.get(code_tax)
            if not name:
                print('Could not find jurisdiction name for %s' % code_tax)
                name = code_tax

            taxcode = self.create_taxcode(name, code_tax)
        return taxcode


def import_boundaries(code_subdivision, boundaries, from_date, company=None):
    sys.stderr.write('Importing boundaries active as of %s' % from_date.isoformat())
    sys.stderr.flush()

    Boundary = Model.get('account.tax.boundary')
    places = get_places(code_subdivision)

    if not company:
        company = get_company()

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

    f = TextIOWrapper(BytesIO(boundaries), encoding='utf-8')
    reader = csv.DictReader(f, fieldnames=_fieldnames,
            restkey='special_districts')
    records = []
    for row in _progress(reader):
        authority = places[row['fips_state_code']]
        start_date = date.fromisoformat(row['start_date'])
        end_date = date.fromisoformat(row['end_date'])
        end_date = None if end_date == date.max else end_date

        taxcode = code_collector.collect(row)
        rule = rule_collector.collect(row)

        seen(rule, code=taxcode)

        if reader.line_num % 10000 == 0:
            Boundary.save(records)
            records = []

        if end_date and end_date <= from_date:
            continue

        record_type = row['record_type']
        record = Boundary(type=record_type,
                          start_date=start_date,
                          end_date=end_date,
                          authority=authority,
                          company=company,
                          rule=rule,
                          code=taxcode)

        if record_type in ('4', 'Z'):
            record.zipcode_low = row['zipcode_low']
            record.zipext_low = row['zipext_low']
            record.zipcode_high = row['zipcode_high']
            record.zipext_high = row['zipext_high']
        elif record_type == 'A':
            record.address_low = row['address_range_low']
            record.address_high = row['address_range_high']
            record.address_parity = row['odd_even_indicator']
            record.street_pre = row['street_pre_directional']
            record.street = row['street_name']
            record.street_suffix = row['street_suffix_abbr']
            record.street_post = row['street_post_directional']
            record.secondary = row['address_secondary_abbr']
            record.secondary_low = row['address_secondary_low']
            record.secondary_high = row['address_secondary_high']
            record.secondary_parity = row['address_secondary_odd_even']
            record.city = row['city_name']
            record.zipcode = row['zipcode']
            record.zipext = row['plus4']
        else:
            print("\nUnknown record type %s: %s" % (record_type, row))

        records.append(record)

    Boundary.save(records)
    print('.', file=sys.stderr)
    return _seen, code_collector

def update_taxcode_taxes(codes, collector):
    sys.stderr.write('Updating taxcode taxes')
    sys.stderr.flush()
    TaxCode = Model.get('account.tax.code')
    TaxRule = Model.get('account.tax.rule')

    _tax_bases = set()
    _indie_codes = set()
    records = []
    for code, rules in _progress(list(codes.items())):
        if isinstance(code, TaxCode):
            taxes = {tax for rule in rules for line in rule.lines for tax in line.tax.childs}
            for tax in sorted(taxes, key=_codesorter):
                TaxCodeCollector.create_lines(code, tax)
            records.append(code)
        elif isinstance(code, TaxRule):
            taxes = [tax for line in code.lines for tax in line.tax.childs]
            _indie_codes.update(taxes)
        else:
            taxes = []

        for tax in taxes:
            if tax.place and tax.place == collector.authority:
                _tax_bases.add(tax)

    indie_codes = sorted(_indie_codes, key=_codesorter)
    for code, taxes in groupby(indie_codes, key=_codesorter):
        peek = next(taxes)
        name = peek.place.name if peek.place else code
        taxcode = collector.create_taxcode(code, name)
        for tax in chain([peek], taxes):
            collector.create_lines(taxcode, tax)
        records.append(taxcode)

    total_sales = collector.total_sales
    for tax in _tax_bases:
        collector.create_lines(total_sales, tax, amount='base')
    records.append(total_sales)

    TaxCode.save(records)
    print('.', file=sys.stderr)

_fips_indices = itemgetter('fips_state_indicator', 'fips_county_code', 'fips_place_code')
_special_code_index = itemgetter(1)
_codesorter = attrgetter('code')


_fieldnames = ['record_type', 'start_date', 'end_date',
    'address_range_low', 'address_range_high', 'odd_even_indicator', 'street_pre_directional',
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
        clean_taxcodes(code_subdivision)
        taxcodes, collector = import_boundaries(
                code_subdivision, fetch(code.upper(), _base), from_date)
        update_taxcode_taxes(taxcodes, collector)




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
