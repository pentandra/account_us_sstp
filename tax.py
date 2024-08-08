from trytond.model import (
        DeactivableMixin, MatchMixin, ModelSQL, ModelView, fields,
        sequence_ordered, tree)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction



class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'
    authority = fields.Many2One('census.place', "Authority",
            domain=[('parent', '=', None)],
            help="The entity that administers this tax")
    jurisdiction = fields.Many2One('census.place', "Jurisdiction",
            states={
                'invisible': Bool(Eval('parent')),
                })
