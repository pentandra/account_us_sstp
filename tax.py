from trytond.model import (
        DeactivableMixin, MatchMixin, ModelSQL, ModelView, fields,
        sequence_ordered, tree)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction

class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'
    _states = {
        'readonly': Bool(Eval('authority', -1)),
        }
    authority = fields.Many2One('census.place', "Authority",
            domain=[('parent', '=', None)], states=_states,
            help="The entity that administers this tax")
    jurisdiction = fields.Many2One('census.place', "Jurisdiction",
            states={
                'invisible': Bool(Eval('parent')),
                'readonly': _states['readonly'],
                })
    sourcing = fields.Selection([
        (None, ""),
        ('intrastate', "In-state Destination"),
        ('interstate', "Out-of-state Destination"),
        ('origin', "Origin"),
        ], "Sourcing", sort=False, states={
            'readonly': _states['readonly'],
            })
    rate_type = fields.Selection([
        (None, ""),
        ('general', "General Rate"),
        ('food', "Food & Drug Rate"),
        ], "Rate Type", sort=False, states={
            'readonly': _states['readonly'],
            })

class TaxBoundary(ModelView, ModelSQL, MatchMixin):
    "Tax Boundary"
    __name__ = 'account.tax.boundary'
    type = fields.Selection([
        ('A', 'Address'),
        ('Z', 'ZIP Code'),
        ('4', 'ZIP+4 Code'),
        ], "Boundary Type")
    start_date = fields.Date("Starting Date")
    end_date = fields.Date("End Date")
    zipcode_low = fields.Char("ZIP Code Low", size=5)
    zipcode_high = fields.Char("ZIP Code High", size=5)
    zipext_low = fields.Char("ZIP+4 Code Low", size=4)
    zipext_high = fields.Char("ZIP+4 Code High", size=4)
    authority = fields.Many2One('census.place', "Authority",
            domain=[('parent', '=', None)],
            help="The entity that administers this tax boundary")
    rule = fields.Many2One('account.tax.rule', "Tax Rule",
            domain=[('authority', '=', Eval('authority', -1))],
            ondelete='RESTRICT')

class TaxRule(metaclass=PoolMeta):
    __name__ = 'account.tax.rule'

    authority = fields.Many2One('census.place', "Authority",
            domain=[('parent', '=', None)],
            help="The entity that administers this tax")
    jurisdiction = fields.Many2One('census.place', "Jurisdiction",
        help="The tax jurisdiction represented by this rule")

