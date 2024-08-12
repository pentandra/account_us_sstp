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

