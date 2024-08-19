import re
from trytond.model import fields
from trytond.pool import Pool, PoolMeta

class SaleLine(metaclass=PoolMeta):
    "Sale Line"
    __name__ = 'sale.line'

    @fields.depends('sale', 'sale_date',
                    '_parent_sale.shipment_address')
    def compute_taxes(self, party):
        pool = Pool()
        Date = pool.get('ir.date')
        Boundary = pool.get('account.tax.boundary')

        sale_date = self.sale_date or Date.today()

        if self.sale and self.sale.shipment_address:
            a = self.sale.shipment_address

            pattern = r'(\d{5})-?(\d{4})?$'
            match = re.match(pattern, a.postal_code)
            if match:
                zipcode, zipext = match.groups()

                try:
                    boundary, = Boundary.search([
                        ('start_date', '<=', sale_date),
                        ['OR', [
                            ('end_date', '>=', sale_date)
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
                    if party and not party.customer_tax_rule:
                        party.customer_tax_rule = boundary.rule

        return super().compute_taxes(party)
