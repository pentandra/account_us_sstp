#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import csv
import os
import sys
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import defaultdict
from datetime import date
from io import BytesIO, TextIOWrapper
from itertools import batched, chain, groupby
from operator import attrgetter, itemgetter
from proteus import Model, config

from .common import _progress, fetch, get_company, get_places


def clean_boundaries(code_subdivision, company=None):
    sys.stderr.write('Cleaning boundaries')
    sys.stderr.flush()

    if not company:
        company = get_company()

    Boundary = Model.get('account.tax.boundary')
    Boundary._proxy.clean([
        ('authority.code', '=', code_subdivision),
        ('company', '=', company),
        ], {})
    print('.', file=sys.stderr)

class TaxRuleCollector:

    def __init__(self, authority, places, company=None):
        self.places = places
        self.taxes = defaultdict(set)
        self.generic_taxes = {}
        self.authority = authority
        self.company = company or get_company()

        TaxRule = Model.get('account.tax.rule')
        try:
            rule, = TaxRule.find([
                        ('name', '=', f"{self.authority.code} Retail"),
                        ('authority', '=', self.authority),
                        ('company', '=', self.company),
                        ('kind', '=', 'sale'),
                        ])
        except ValueError:
            rule = TaxRule(name=f"{self.authority.code} Retail",
                           kind='sale',
                           company=self.company,
                           authority=self.authority)
            rule.save()

        self.rule = rule

    def get_taxes(self, code, authority):
        taxes = self.taxes.get(code)
        if not taxes:
            Tax = Model.get('account.tax')
            taxes = Tax.find([
                ('authority', '=', authority),
                ('company', '=', self.company),
                ('code', '=', code),
                ('type', '=', 'none'),
                ('parent', '=', None),
                ])
            self.taxes[code] = set(taxes)
        return self.taxes[code]

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
                # create tax
                generic_tax, = Tax.duplicate([tax], default={
                    'description': str(tax.name),
                    'childs': None,
                    'sourcing': None,
                })
                generic_tax.save()

            self.generic_taxes[tax.id] = generic_tax
        return generic_tax

    def collect(self, row):
        authority = self.places[row['fips_state_code']]
        fips_codes = _fips_indices(row)
        special_codes = map(_special_code_index,
                            batched(row['special_districts'], n=3))
        codes = tuple(filter(None, chain(fips_codes, special_codes)))
        taxes = set()
        for code in codes:
            if all(c == '0' for c in code):
                continue
            taxes |= self.get_taxes(code, authority)
        return '-'.join(codes), taxes


class TaxCodeCollector:

    def __init__(self, code_subdivision, authority, places, company=None):
        self.taxcodes = {}
        self.authority = authority
        self.places = places
        self.company = company or get_company()

        codenames = os.path.join(os.path.dirname(__file__), 'codenames.csv')
        if os.path.isfile(codenames):
            with open(codenames, newline='') as csvfile:
                reader = csv.DictReader(
                        csvfile, fieldnames=['code', 'code_tax', 'name'])
                self.names = {r['code_tax']: r['name']
                              for r in reader if r['code'] == code_subdivision}

        TaxCode = Model.get('account.tax.code')
        root = self.get_taxcode(self.authority.code)
        if not root:
            root = TaxCode(name="%s Streamlined Sales and Use Tax Report" % (
                                        self.authority.name),
                           code=self.authority.code,
                           company=self.company,
                           authority=self.authority)
            root.save()

        try:
            taxable_sales, = root.childs.find([
                ('name', '=', 'Taxable Sales'),
                ])
        except ValueError:
            taxable_sales = root.childs.new()
            taxable_sales.name = "Taxable Sales"
            taxable_sales.code = 'A'
            taxable_sales.authority = self.authority
            taxable_sales.company = self.company
            taxable_sales.save()

        try:
            total_sales, = taxable_sales.childs.find([
                ('name', '=', 'Total Sales'),
                ])
        except ValueError:
            total_sales = taxable_sales.childs.new()
            total_sales.name = "Total Sales"
            total_sales.code = '1'
            total_sales.authority = self.authority
            total_sales.company = self.company
            total_sales.save()

        try:
            exemptions, = taxable_sales.childs.find([
                ('name', '=', 'Exemptions and Deductions'),
                ])
        except ValueError:
            exemptions = taxable_sales.childs.new()
            exemptions.name = "Exemptions and Deductions"
            exemptions.code = '2'
            exemptions.authority = self.authority
            exemptions.company = self.company
            exemptions.save()

        for name in ['Agriculture', 'Direct Pay',
                     'Government Exemption Organizations', 'Manufacturing',
                     'Resale', 'Other']:
            try:
                subcode, = exemptions.childs.find([('name', '=', name)])
            except ValueError:
                subcode = exemptions.childs.new()
                subcode.name = name
                subcode.authority = self.authority
                subcode.company = self.company
                subcode.save()

        try:
            total_tax, = root.childs.find([
                ('name', '=', 'Total Tax Due'),
                ])
        except ValueError:
            total_tax = root.childs.new()
            total_tax.name = "Total Tax Due"
            total_tax.code = 'B'
            total_tax.authority = self.authority
            total_tax.company = self.company
            total_tax.save()

        try:
            state_tax_due, = total_tax.childs.find([
                ('name', '=', 'State Tax Due'),
                ])
        except ValueError:
            state_tax_due = total_tax.childs.new()
            state_tax_due.name = "State Tax Due"
            state_tax_due.code = '1'
            state_tax_due.authority = self.authority
            state_tax_due.company = self.company
            state_tax_due.save()

        try:
            jurisdiction_detail, = total_tax.childs.find([
                ('name', '=', 'Jurisdiction Detail'),
                ])
        except ValueError:
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
        if code_tax == self.authority.code_fips:
            return self.state_tax_due

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

    def create_jurisdictional_taxcode(self, code):
        taxcode = self.jurisdiction_detail.childs.new()
        taxcode.code = code
        taxcode.authority = self.authority
        taxcode.company = self.company
        return taxcode

    def create_lines(self, code, tax, amount='tax'):
        for op, account_type in zip(['+', '-'], ['invoice', 'credit']):
            line = code.lines.new()
            line.operator = op
            line.tax = tax
            line.amount = amount
            line.type = account_type
            line.authority = self.authority

    def collect(self, row):
        code_tax = row['composite_ser_code']
        if not code_tax or all(c == '0' for c in code_tax):
            return

        taxcode = self.get_taxcode(code_tax)
        if not taxcode:
            taxcode = self.create_jurisdictional_taxcode(code_tax)

            if self.names.get(code_tax):
                taxcode.name = self.names[code_tax]
            else:
                print('Could not find jurisdiction name for %s' % code_tax,
                      file=sys.stderr)
                taxcode.name = code_tax

            taxcode.save()
        return taxcode


def import_boundaries(code_subdivision, boundaries, from_date, company=None):
    sys.stderr.write(
            "Importing boundaries active as of %s" % from_date.isoformat())
    sys.stderr.flush()

    Boundary = Model.get('account.tax.boundary')
    places = get_places(code_subdivision)

    authority = None
    try:
        authority, = [v for v in places.values() if not v.parent]
    except ValueError:
        sys.exit(
            "\nError could not find a state authority for the code: %s" % (
                code_subdivision))

    if not company:
        company = get_company()

    rule_collector = TaxRuleCollector(authority, places, company)
    code_collector = TaxCodeCollector(
        code_subdivision, authority, places, company)

    def get_tax_key(value, authority):
        tax_key = _tax_keys.get(value)
        if not tax_key:
            TaxKey = Model.get('account.tax.boundary.tax_key')
            try:
                tax_key, = TaxKey.find([
                    ('authority', '=', authority.id),
                    ('value', '=', value),
                ])
            except ValueError:
                tax_key = TaxKey(value=value, authority=authority)
                tax_key.save()
            _tax_keys[value] = tax_key
        return tax_key
    _tax_keys = {}

    def seen(taxes, code=None):
        if _seen.get(code) and taxes <= _seen[code]:
            return True
        _seen[code] |= taxes
        return False
    _seen = defaultdict(set)

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
        tax_key, taxes = rule_collector.collect(row)

        seen(taxes, code=taxcode or tax_key)

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
                          tax_key=get_tax_key(tax_key, authority),
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
            print("\nUnknown record type '%s' on line %s" % (
                record_type, reader.line_num), file=sys.stderr)

        records.append(record)

    Boundary.save(records)
    print('.', file=sys.stderr)
    return _seen, code_collector, rule_collector


def update_taxcode_taxes(taxcodes, collector):
    sys.stderr.write('Updating tax code taxes')
    sys.stderr.flush()
    TaxCode = Model.get('account.tax.code')

    _codegetter = attrgetter('code')
    _tax_bases = set()
    _indie_codes = set()
    records = []
    for taxcode, taxes in _progress(list(taxcodes.items())):
        taxes = {c for tax in taxes for c in tax.childs}
        if isinstance(taxcode, TaxCode):
            for tax in sorted(taxes, key=_codegetter):
                # update name?
                if tax not in [line.tax for line in taxcode.lines]:
                    collector.create_lines(taxcode, tax)
            records.append(taxcode)
        elif isinstance(taxcode, str):
            _indie_codes.update(taxes)

        for tax in taxes:
            if tax.place and tax.place == collector.authority:
                _tax_bases.add(tax)

    indie_codes = sorted(_indie_codes, key=_codegetter)
    for code_tax, iter_tax in groupby(indie_codes, key=_codegetter):
        taxcode = collector.get_taxcode(code_tax)
        taxes = list(iter_tax)
        if not taxcode:
            peek = taxes[0]
            if hasattr(peek, 'place') and hasattr(peek.place, 'name'):
                name = peek.place.name
            else:
                name = code_tax
            taxcode = collector.create_jurisdictional_taxcode(code_tax)
            taxcode.name = name
            taxcode.save()  # initial save
        for tax in taxes:
            if tax not in [line.tax for line in taxcode.lines]:
                collector.create_lines(taxcode, tax)
        records.append(taxcode)

    total_sales = collector.total_sales
    for tax in _tax_bases:
        if tax not in [line.tax for line in total_sales.lines]:
            collector.create_lines(total_sales, tax, amount='base')
    records.append(total_sales)

    TaxCode.save(records)
    print('.', file=sys.stderr)

def update_tax_rule_lines(collector):
    sys.stderr.write('Updating tax rule lines (by code)')
    sys.stderr.flush()
    TaxRuleLine = Model.get('account.tax.rule.line')

    def get_rule_lines(code):
        lines = TaxRuleLine.find([
            ('rule', '=', collector.rule.id),
            ('authority', '=', collector.authority),
            ('tax.code', '=', code),
        ])
        return {l.tax: l for l in lines}

    records = []
    for code, taxes in _progress(
            sorted(collector.taxes.items(), key=lambda c: (len(c), c))):
        lines = get_rule_lines(code)
        for tax in sorted(taxes, key=int):
            if tax not in lines:
                origin_tax = collector.get_generic_tax(tax)
                authority = collector.authority

                line = collector.rule.lines.new()
                line.authority = authority
                line.group = tax.group
                line.origin_tax = origin_tax
                line.tax = tax
                line.to_country = line.from_country = authority.country
                line.to_subdivision = authority
                if tax.sourcing == 'intrastate':
                    line.from_subdivision = authority
                else:
                    line.from_subdivision = None
                records.append(line)

    TaxRuleLine.save(records)
    print('.', file=sys.stderr)

_fips_indices = itemgetter(
        'fips_state_indicator', 'fips_county_code', 'fips_place_code')
_special_code_index = itemgetter(1)


_fieldnames = ['record_type', 'start_date', 'end_date',
    'address_range_low', 'address_range_high', 'odd_even_indicator',
    'street_pre_directional', 'street_name', 'street_suffix_abbr',
    'street_post_directional', 'address_secondary_abbr',
    'address_secondary_low', 'address_secondary_high',
    'address_secondary_odd_even', 'city_name', 'zipcode', 'plus4',
    'zipcode_low', 'zipext_low', 'zipcode_high', 'zipext_high',
    'composite_ser_code', 'fips_state_code', 'fips_state_indicator',
    'fips_county_code', 'fips_place_code', 'fips_place_class_code',
    'longitude', 'latitude']

_base = 'https://www.streamlinedsalestax.org/ratesandboundry/Boundary/'


def main(database, codes, from_date, config_file=None):
    config.set_trytond(database, config_file=config_file)
    with config.get_config().set_context(active_test=False):
        do_import(codes, from_date)


def do_import(codes, from_date):
    for code in codes:
        print(code, file=sys.stderr)
        code_subdivision = 'US-%s' % code.upper()

        clean_boundaries(code_subdivision)
        taxcodes, code_collector, rule_collector = import_boundaries(
                code_subdivision, fetch(code.upper(), _base), from_date)
        update_taxcode_taxes(taxcodes, code_collector)
        update_tax_rule_lines(rule_collector)


def run():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--database', dest='database', required=True)
    parser.add_argument('-c', '--config', dest='config_file',
        help="the trytond config file")
    parser.add_argument('-f', '--from', dest='from_date',
        default=date.today().isoformat(), type=date.fromisoformat,
        help="import all boundary records active from the given date "
        "YYYY-MM-DD")
    parser.add_argument('--all', action='store_true',
        help="import all available boundary records (overrides --from)")
    parser.add_argument('codes', nargs='+')

    args = parser.parse_args()
    from_date = date.min if args.all else args.from_date
    main(args.database, args.codes, from_date, args.config_file)


if __name__ == '__main__':
    run()
