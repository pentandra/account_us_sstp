#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import csv
from datetime import date
from decimal import Decimal
import os
import sys

from argparse import ArgumentParser
from io import BytesIO, TextIOWrapper
from proteus import Model, config

from common import fetch, get_company, get_places, _progress


def get_taxes(code_subdivision, company):
    Tax = Model.get('account.tax')
    return {(t.name, t.start_date): t for t in Tax.find([
        ('authority.subdivision.code', '=', code_subdivision),
        ('company', '=', company.id),
        ])}

def get_groups():
    TaxGroup = Model.get('account.tax.group')
    return {g.code: g for g in TaxGroup.find([])}

def get_tax_account(name, company):
    Account = Model.get('account.account')

    return Account.find([
        ('company', '=', company.id),
        ['OR',
         [('name', '=', name)],
         [('code', '=', name)],
         ],
        ], limit=1)

def update_taxes(code_subdivision, stream, from_date, account):
    print('Importing rates active as of %s' % from_date.isoformat(), file=sys.stderr)
    Tax = Model.get('account.tax')

    places = get_places(code_subdivision)
    groups = get_groups()
    company = get_company()
    taxes = get_taxes(code_subdivision, company)
    tax_account, = get_tax_account(account, company)

    today = date.today()
    far_future = today.replace(year=today.year + 100)

    f = TextIOWrapper(BytesIO(stream), encoding='utf-8-sig')
    records = []
    current_code_fips = None
    for row in _progress(list(csv.DictReader(f, fieldnames=_fieldnames))):
        authority = places[row['state']]
        code_fips = row['jurisdiction_fips_code']
        place = places.get(row['jurisdiction_fips_code'])
        group = groups[row['jurisdiction_type']]
        start_date = date.fromisoformat(row['start_date'])
        end_date = date.fromisoformat(row['end_date'])

        sequence = None
        if place:
            match place.level:
                case 'state':
                    sequence = 0
                case 'county':
                    sequence = 1
                case 'place':
                    sequence = 2

        for type_ in ['general_rate_intrastate', 'general_rate_interstate',
            'food_rate_intrastate', 'food_rate_interstate']:
            name = '%s %s' % (code_fips, type_) #TODO: isn't there a better name?
            sourcing = 'intrastate' if 'intrastate' in type_ else 'interstate'
            rate_type = 'general' if 'general' in type_ else 'food'

            if current_code_fips != code_fips:
                if (name, None) in taxes:
                    parent = taxes[(name, None)]
                else:
                    parent = Tax(name=name)

                parent.code = code_fips
                parent.place = place
                parent.description = '%s tax' % place.name if place else code_fips
                parent.authority = authority
                parent.type = 'none'
                parent.group = group
                parent.company = company
                parent.sourcing = sourcing
                parent.rate_type = rate_type
                parent.sequence = sequence

                records.append(parent)

            if end_date and end_date <= from_date:
                continue # import the parent at least for complete tax rules

            if (name, start_date) in taxes:
                record = taxes[(name, start_date)]
            else:
                record = Tax(name=name)

            record.code = code_fips
            record.place = place
            record.description = '%s tax (%s)' % (place.name if place else code_fips,
                                                  row[type_])
            record.authority = authority
            record.type = 'percentage'
            record.group = group
            record.company = company
            record.rate = Decimal(row[type_])
            record.sourcing = sourcing
            record.rate_type = rate_type
            record.start_date = start_date
            record.end_date = None if end_date > far_future else end_date
            record.invoice_account = tax_account
            record.credit_note_account = tax_account
            record.sequence = sequence

            records.append(record)
        current_code_fips = code_fips

    Tax.save(records)
    return {(r.name, r.start_date): r for r in records}

def update_taxes_parent(taxes):
    print("Update taxes parent", file=sys.stderr)
    Tax = Model.get('account.tax')

    records = []
    for k, record in _progress(taxes.items()):
        if record.type == 'none':
            continue

        name, start_date = k
        record.parent = taxes[(name, None)]
        records.append(record)
    Tax.save(records)

_fieldnames = ['state', 'jurisdiction_type', 'jurisdiction_fips_code',
    'general_rate_intrastate', 'general_rate_interstate',
    'food_rate_intrastate', 'food_rate_interstate', 'start_date', 'end_date']

_base = 'https://www.streamlinedsalestax.org/ratesandboundry/Rates/'

def main(database, args, config_file=None):
    config.set_trytond(database, config_file=config_file)
    do_import(args)


def do_import(args):
    for code in args.codes:
        print(code, file=sys.stderr)
        if args.account[-1] in ['-', '–', '—']:
            account = args.account + code.upper()
        else:
            account = args.account
        from_date = date.min if args.all else args.from_date
        code_subdivision = 'US-%s' % code.upper()
        taxes = update_taxes(code_subdivision, fetch(code.upper(), _base), from_date, account)
        update_taxes_parent(taxes)


def run():
    parser = ArgumentParser()
    parser.add_argument('-d', '--database', dest='database', required=True)
    parser.add_argument('-c', '--config', dest='config_file',
        help='the trytond config file')
    parser.add_argument('-l', '--liability-account', dest='account', default='2230-',
        help='the code of the invoice and credit note account related to the taxes '
        '(defaults to 2230-{code}, see the account_us module)')
    parser.add_argument('-f', '--from', dest='from_date',
        default=date.today().isoformat(), type=date.fromisoformat,
        help='import all taxes active from the given date YYYY-MM-DD '
             '(defaults to %s)' % date.today().isoformat())
    parser.add_argument('--all', action='store_true',
        help='import all available taxes (overrides --from)')
    parser.add_argument('codes', nargs='+')

    args = parser.parse_args()
    main(args.database, args, args.config_file)


if __name__ == '__main__':
    run()
