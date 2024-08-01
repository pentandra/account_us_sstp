# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

__all__ = ['register']


def register():
    # Prevent import of backend when importing scripts
    from . import census
    Pool.register(
        census.Region,
        census.ClassCode,
        census.Place,
        module='account_us_sstp', type_='model')
    Pool.register(
        module='account_us_sstp', type_='wizard')
    Pool.register(
        module='account_us_sstp', type_='report')
