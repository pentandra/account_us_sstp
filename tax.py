from trytond.model import (
        MatchMixin, ModelSQL, ModelView, fields)
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
    del _states

    @classmethod
    def copy(cls, taxes, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('authority', None)
        return super().copy(taxes, default=default)

    @classmethod
    def _amount_where(cls, tax_line, move_line, move):
        where = super()._amount_where(tax_line, move_line, move)

        context = Transaction().context
        code_id = context.get('code')
        amount = context.get('amount')

        if code_id and amount == 'tax':
            TaxCode = Pool().get('account.tax.code')
            code = TaxCode(code_id)
            return where & (tax_line.code == code.code)
        else:
            return where


class TaxBoundary(ModelView, ModelSQL, MatchMixin):
    "Tax Boundary"
    __name__ = 'account.tax.boundary'
    type = fields.Selection([
        ('A', 'Address'),
        ('Z', 'ZIP Code'),
        ('4', 'ZIP+4 Code'),
        ], "Boundary Type", required=True)
    start_date = fields.Date("Starting Date", required=True)
    end_date = fields.Date("End Date")
    zipcode_low = fields.Char("ZIP Code Low", size=5, states={
        'required': Eval('type').in_(['Z', '4']),
        })
    zipcode_high = fields.Char("ZIP Code High", size=5, states={
        'required': Eval('type').in_(['Z', '4']),
        })
    zipext_low = fields.Char("ZIP+4 Code Low", size=4, states={
        'required': Eval('type') == '4',
        })
    zipext_high = fields.Char("ZIP+4 Code High", size=4, states={
        'required': Eval('type') == '4',
        })
    authority = fields.Many2One('census.place', "Authority",
            domain=[('parent', '=', None)], required=True,
            help="The entity that administers this tax boundary")
    rule = fields.Many2One('account.tax.rule', "Tax Rule",
            domain=[
                ('authority', '=', Eval('authority', -1))
                ],
            ondelete='RESTRICT', required=True)
    code = fields.Many2One('account.tax.code', "Tax Code",
            domain=[
                ('authority', '=', Eval('authority', -1))
                ],
            ondelete='RESTRICT')

class TaxCode(metaclass=PoolMeta):
    "Tax Code"
    __name__ = 'account.tax.code'
    authority = fields.Many2One('census.place', "Authority",
            domain=[('parent', '=', None)],
            help="The entity that administers this tax code")


class TaxCodeLine(metaclass=PoolMeta):
    "Tax Code Line"
    __name__ = 'account.tax.code.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.tax.context['code'] = Eval('code')
        cls.tax.depends.add('code')
        cls.tax.context['amount'] = Eval('amount')
        cls.tax.depends.add('amount')
        cls.code.ondelete = 'CASCADE'

    @property
    def _line_domain(self):
        domain = super()._line_domain
        domain.append(['OR',
            [('code', '=', self.code.code)],
            [('type', '=', 'base')],
            ])
        return domain


class TaxLine(metaclass=PoolMeta):
    "Tax Line"
    __name__ = 'account.tax.line'
    code = fields.Char("Reporting Code")

class TaxRule(metaclass=PoolMeta):
    __name__ = 'account.tax.rule'

    authority = fields.Many2One('census.place', "Authority",
            domain=[('parent', '=', None)],
            help="The entity that administers this tax")
    jurisdiction = fields.Many2One('census.place', "Jurisdiction",
        help="The tax jurisdiction represented by this rule")

    @classmethod
    def copy(cls, rules, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('authority', None)
        return super().copy(rules, default=default)

