#!/usr/bin/env python3

import csv
import sys
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import namedtuple
from datetime import date
from decimal import Decimal
from io import BytesIO, TextIOWrapper
from proteus import Model, config

from .common import _progress, fetch, get_company, get_places

_TaxKey = namedtuple('_TaxKey',
                     ['code', 'sourcing', 'product_class', 'start_date'])


def get_taxes(code_subdivision, company):
    Tax = Model.get('account.tax')
    return {(t.code, t.sourcing, t.product_class, t.start_date): t
            for t in Tax.find([
                ('authority.code', '=', code_subdivision),
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
    print("Importing rates active as of ", from_date.isoformat(),
          file=sys.stderr)
    Tax = Model.get('account.tax')

    places = get_places(code_subdivision)
    groups = get_groups()
    company = get_company()
    taxes = get_taxes(code_subdivision, company)
    tax_account, = get_tax_account(account, company)

    today = date.today()
    far_future = today.replace(year=today.year + 50)

    _seen = set()

    def seen(key):
        if key in _seen:
            return True
        _seen.add(_TaxKey._make(key))
        return False

    f = TextIOWrapper(BytesIO(stream), encoding='utf-8-sig')
    records = []
    for row in _progress(list(csv.DictReader(f, fieldnames=_fieldnames))):
        authority = places[row['state']]
        code_tax = row['jurisdiction_fips_code']
        place = places.get(row['jurisdiction_fips_code'])
        group = groups[row['jurisdiction_type']]
        start_date = date.fromisoformat(row['start_date'])
        end_date = date.fromisoformat(row['end_date'])

        sequence = None
        if place:
            match place.fips_level:
                case 'state':
                    sequence = 0
                case 'county':
                    sequence = 1
                case 'place':
                    sequence = 2

        for type_ in ['general_rate_intrastate', 'general_rate_interstate',
                      'food_rate_intrastate', 'food_rate_interstate']:
            name = "Uniform sales and use tax"
            sourcing = 'intrastate' if 'intrastate' in type_ else 'interstate'
            product_class = 'general' if 'general' in type_ else 'food'

            if not seen((code_tax, sourcing, product_class, None)):

                if (code_tax, sourcing, product_class, None) in taxes:
                    parent = taxes[(code_tax, sourcing, product_class, None)]
                else:
                    parent = Tax(code=code_tax,
                                 sourcing=sourcing,
                                 product_class=product_class,
                                 start_date=None)

                parent.name = name
                parent.description = '%s tax' % (
                        place.name if place else code_tax)
                parent.authority = authority
                parent.place = place
                parent.type = 'none'
                parent.group = group
                parent.company = company
                parent.sequence = sequence

                records.append(parent)

            if end_date and end_date <= from_date:
                continue  # import the parent at least for complete tax rules

            if (code_tax, sourcing, product_class, start_date) in taxes:
                record = taxes[(code_tax, sourcing, product_class, start_date)]
            else:
                record = Tax(code=code_tax,
                             sourcing=sourcing,
                             product_class=product_class,
                             start_date=start_date)

            record.name = "%s (%s)" % (
                    name, format(Decimal(row[type_]), '.2%'))
            record.place = place
            record.description = '%s tax (%s)' % (
                    place.name if place else code_tax,
                    format(Decimal(row[type_]), '.2%'))
            record.authority = authority
            record.type = 'percentage'
            record.group = group
            record.company = company
            record.rate = Decimal(row[type_])
            record.end_date = None if end_date > far_future else end_date
            record.invoice_account = tax_account
            record.credit_note_account = tax_account
            record.sequence = sequence

            records.append(record)

    Tax.save(records)
    return {(r.code, r.sourcing, r.product_class, r.start_date): r
            for r in records}


def update_taxes_parent(taxes):
    print("Update taxes parent", file=sys.stderr)
    Tax = Model.get('account.tax')

    records = []
    for k, record in _progress(taxes.items()):
        if record.type == 'none':
            continue

        code, sourcing, product_class, _ = k
        record.parent = taxes[(code, sourcing, product_class, None)]
        records.append(record)
    Tax.save(records)


_fieldnames = ['state', 'jurisdiction_type', 'jurisdiction_fips_code',
    'general_rate_intrastate', 'general_rate_interstate',
    'food_rate_intrastate', 'food_rate_interstate', 'start_date', 'end_date']

_base = 'https://www.streamlinedsalestax.org/ratesandboundry/Rates/'


def main(database, codes, from_date, account, config_file=None):
    config.set_trytond(database, config_file=config_file)
    with config.get_config().set_context(active_test=False):
        do_import(codes, from_date, account)


def do_import(codes, from_date, account):
    for code in codes:
        print(code, file=sys.stderr)
        if str(account)[-1] in ['-', '–', '—']:
            account = account + code.upper()
        code_subdivision = 'US-%s' % code.upper()
        taxes = update_taxes(code_subdivision,
                             fetch(code.upper(), _base), from_date, account)
        update_taxes_parent(taxes)


def run():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--database', dest='database', required=True)
    parser.add_argument('-c', '--config', dest='config_file',
        help="the trytond config file")
    parser.add_argument('-l', '--liability-account', dest='account',
        default='2230-', help="the code of the invoice and credit note "
        "account related to the taxes")
    parser.add_argument('-f', '--from', dest='from_date',
        default=date.today().isoformat(), type=date.fromisoformat,
        help="import all taxes active from the given date YYYY-MM-DD")
    parser.add_argument('--all', action='store_true',
        help="import all available taxes (overrides --from)")
    parser.add_argument('codes', nargs='+')

    args = parser.parse_args()
    from_date = date.min if args.all else args.from_date
    main(args.database, args.codes, from_date, args.account, args.config_file)


if __name__ == '__main__':
    run()
