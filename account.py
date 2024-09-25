import logging
import re

import usaddress

from trytond.model import fields
from trytond.pool import Pool, PoolMeta

logger = logging.getLogger(__name__)


class BoundaryLocatorMixin:
    __slots__ = ()

    @staticmethod
    def get_boundary(address, date):
        if not address.country or address.country.code != 'US':
            return

        pool = Pool()
        Boundary = pool.get('account.tax.boundary')

        try:
            address_tagged, address_type = usaddress.tag(address.full_address)
        except usaddress.RepeatedLabelError as e:
            logger.debug(f"Trouble parsing address {address.rec_name}: "
                         f"'{e.original_string}' as '{e.parsed_string}'")
            return

        address_domain = [('type', '=', 'A')]

        if address_type == 'Street Address':
            address_number = address_tagged.get('AddressNumber')
            # Secondary address doesn't seem to currently be used by any states
            # secondary_number = address_tagged.get('OccupancyIdentifier')

            address_domain.extend([
                ('address_low', '<=', address_number),
                ('address_high', '>=', address_number),
                ('street', 'ilike', address_tagged.get('StreetName')),
                ])

            if int(address_number) % 2 == 0:
                address_domain.append(('address_parity', 'in', ['B', 'E']))
            else:
                address_domain.append(('address_parity', 'in', ['B', 'O']))

            for tag, field in [('StreetNamePreDirectional', 'street_pre'),
                               ('StreetNamePostDirectional', 'street_post'),
                               ('StreetNamePostType', 'street_suffix')]:
                if address_tagged.get(tag):
                    address_domain.extend([
                            (field, 'ilike', address_tagged[tag]),
                            ])
                else:
                    address_domain.append((field, 'in', [None, '']))

        elif address_type == 'PO Box':
            box_id = address_tagged.get('USPSBoxID')
            address_domain.extend([
                ('address_low', '<=', box_id),
                ('address_high', '>=', box_id),
                ('address_parity', 'in', [None, ''] + ['B']),
                ('street', 'ilike', address_tagged.get('USPSBoxType')),
                ('street_pre', 'in', [None, '']),
                ('street_post', 'in', [None, '']),
                ])
        else:
            logger.warning("Recieved '%s' address without handler: %s",
                        address_type, address_tagged)

        _zipcode_pattern = r'(\d{5})-?(\d{4})?$'
        match_zip = re.match(_zipcode_pattern, address.postal_code)
        if match_zip:
            zipcode, zipext = match_zip.groups()
        else:
            zipcode = zipext = None

        address_domain.extend([
                ('city', 'ilike', address.city),
                ('zipcode', '=', zipcode),
                ])

        if zipext:
            address_domain.append(('zipext', '=', zipext))

        boundaries = Boundary.search([
            ('start_date', '<=', date),
            ['OR',
                [('end_date', '>=', date)],
                [('end_date', '=', None)],
             ],
            ('authority.country', '=', address.country),
            ('authority', '=', address.subdivision),
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
                address_domain,
             ]
            ])

        for record_type in ['A', '4', 'Z']:
            for boundary in boundaries:
                if boundary.type == record_type:
                    logger.debug(
                        "Returning a '%s' tax boundary %s for %s "
                        "(%s boundaries found)", record_type, boundary.id,
                        address.rec_name, len(boundaries))
                    return boundary


class InvoiceLine(BoundaryLocatorMixin, metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('_parent_invoice.invoice_address')
    def _get_tax_rule_pattern(self):
        pool = Pool()
        pattern = super()._get_tax_rule_pattern()

        Date = pool.get('ir.date')

        if self.tax_date:
            tax_date = self.tax_date
        elif self.invoice and self.invoice.tax_date:
            tax_date = self.invoice.tax_date
        else:
            tax_date = Date.today()

        if self.invoice and self.invoice.invoice_address:
            boundary = self.get_boundary(
                self.invoice.invoice_address, tax_date)

        pattern['tax_key'] = (
            boundary.tax_key if boundary and boundary.tax_key else None)

        return pattern


class InvoiceTax(BoundaryLocatorMixin, metaclass=PoolMeta):
    __name__ = 'account.invoice.tax'

    def get_move_lines(self):
        """
        Add code to tax lines, if located boundary has code.
        """
        lines = super().get_move_lines()

        pool = Pool()
        Date = pool.get('ir.date')

        if (getattr(self, 'invoice', None)
            and getattr(self.invoice, 'tax_date', None)):
            tax_date = self.invoice.tax_date
        else:
            tax_date = Date.today()

        if (getattr(self, 'invoice', None)
                and getattr(self.invoice, 'invoice_address', None)):
            address = self.invoice.invoice_address

            boundary = self.get_boundary(address, tax_date)

            if boundary and boundary.code:
                for line in lines:
                    for tax_line in line.tax_lines:
                        if tax_line.type == 'tax':
                            tax_line.code = boundary.code.code

        return lines
