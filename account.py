# This file is part of Tryon. The COPYRIGHT file at the top level of
# this repository contains the full copyright noties and license terms.
import re
from trytond.model import fields
from trytond.pool import Pool, PoolMeta

class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends(
            '_parent_invoice.party', 'party', 'invoice', 'tax_date',
            '_parent_invoice.accounting_date', '_parent_invoice.invoice_date',
            '_parent_invoice.invoice_address') 
    def on_change_product(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Boundary = pool.get('account.tax.boundary')

        if self.invoice and self.invoice.tax_date:
            tax_date = self.invoice.tax_date
        elif self.tax_date:
            tax_date = self.tax_date
        elif self.taxes_date:
            tax_date = self.taxes_date

        if self.invoice and self.invoice.invoice_address:
            a = self.invoice.invoice_address

            pattern = r'(\d{5})-?(\d{4})?$'
            match = re.match(pattern, a.postal_code)
            if match:
                zipcode, zipext = match.groups()

                try:
                    boundary, = Boundary.search([
                        ('start_date', '<=', tax_date),
                        ['OR', [
                            ('end_date', '>=', tax_date)
                            ], [
                            ('end_date', '=', None)
                            ],
                         ],
                        ('authority.country', '=', a.country),
                        ('authority.subdivision', '=', a.subdivision),
                        ['OR', [
                            ('type', '=', '4'),
                            ('zipcode_low', '<=', zipcode),
                            ('zipcode_high', '>=', zipcode),
                            ('zipext_low', '<=', zipext),
                            ('zipext_high', '>=', zipext),
                            ], [
                            ('type', '=', 'Z'),
                            ('zipcode_low', '<=', zipcode),
                            ('zipcode_high', '>=', zipcode),
                            ],
                         ]
                        ], limit=1, order=[('type', 'DESC')])
                except ValueError:
                    boundary = None

                if boundary and boundary.rule:
                    if self.invoice and self.invoice.party:
                        party = self.invoice.party
                    elif self.party:
                        party = self.party
                    if not party.customer_tax_rule:
                        party.customer_tax_rule = boundary.rule

        return super().on_change_product()
