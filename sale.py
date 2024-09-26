from trytond.model import fields
from trytond.pool import Pool, PoolMeta

from .account import BoundaryLocatorMixin


class SaleLine(BoundaryLocatorMixin, metaclass=PoolMeta):
    __name__ = 'sale.line'

    @fields.depends('sale', 'sale_date',
                    '_parent_sale.shipment_address')
    def _get_tax_rule_pattern(self):
        pool = Pool()
        Date = pool.get('ir.date')

        pattern = super()._get_tax_rule_pattern()

        sale_date = self.sale_date or Date.today()

        tax_key = None
        if self.sale and self.sale.shipment_address:
            boundary = self.get_boundary(
                self.sale.shipment_address, sale_date)
            if boundary:
                tax_key = boundary.tax_key

        pattern['tax_key'] = tax_key.id if tax_key else None

        return pattern
