from trytond.model import fields
from trytond.pool import Pool, PoolMeta

from .account import BoundaryLocatorMixin


class SaleLine(BoundaryLocatorMixin, metaclass=PoolMeta):
    __name__ = 'sale.line'

    @fields.depends('sale', 'sale_date',
                    '_parent_sale.shipment_address')
    def compute_taxes(self, party):
        """
        Temporarily set customer tax rule, if boundary located.
        """
        pool = Pool()
        Date = pool.get('ir.date')

        sale_date = self.sale_date or Date.today()

        if (getattr(self, 'sale', None)
            and getattr(self.sale, 'shipment_address', None)):
            address = self.sale.shipment_address

            boundary = self.get_boundary(address, sale_date)

            if boundary and boundary.rule:
                if party and not party.customer_tax_rule:
                    party.customer_tax_rule = boundary.rule

        return super().compute_taxes(party)
