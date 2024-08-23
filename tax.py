from decimal import Decimal

from sql import Literal
from sql.aggregate import Sum
from sql.conditionals import Case

from trytond import backend
from trytond.model import (
        MatchMixin, ModelSQL, ModelView, fields)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.tools import cursor_dict
from trytond.transaction import Transaction

class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'
    _states = {
        'readonly': Bool(Eval('authority', -1)),
        }
    authority = fields.Many2One('census.place', "Authority",
            domain=[('parent', '=', None)], states=_states,
            help="The entity that administers this tax")
    place = fields.Many2One('census.place', "Related Place",
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
    def get_amount(cls, taxes, names):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        TaxLine = pool.get('account.tax.line')
        Tax = pool.get('account.tax')
        cursor = Transaction().connection.cursor()

        move = Move.__table__()
        move_line = MoveLine.__table__()
        tax_line = TaxLine.__table__()
        tax = Tax.__table__()

        tax_ids = list(map(int, taxes))
        result = {}
        for name in names:
            result[name] = dict.fromkeys(tax_ids, Decimal(0))

        columns = []
        amount = tax_line.amount
        debit = move_line.debit
        credit = move_line.credit
        if backend.name == 'sqlite':
            amount = TaxLine.amount.sql_cast(tax_line.amount)
            debit = MoveLine.debit.sql_cast(debit)
            credit = MoveLine.credit.sql_cast(credit)
        is_invoice = (
            ((amount > 0) & ((debit > 0) | (credit > 0)))
            | ((amount < 0) & ((debit < 0) | (credit < 0)))
            )
        is_credit = (
            ((amount < 0) & ((debit > 0) | (credit > 0)))
            | ((amount > 0) & ((debit < 0) | (credit < 0)))
            )
        for name, clause in [
                ('invoice_base_amount',
                    is_invoice & (tax_line.type == 'base')),
                ('invoice_tax_amount',
                    is_invoice & (tax_line.type == 'tax')),
                ('credit_base_amount',
                    is_credit & (tax_line.type == 'base')),
                ('credit_tax_amount',
                    is_credit & (tax_line.type == 'tax')),
                ]:
            if name not in names:
                continue
            if backend.name == 'postgresql': # FIXME
                columns.append(Sum(amount, filter_=clause).as_(name))
            else:
                columns.append(Sum(Case([clause, amount])).as_(name))

        where = cls._amount_where(tax_line, move_line, move)
        where_tax = cls._amount_where_tax(tax_line, move_line, move, tax)
        query = (tax_line
            .join(move_line, condition=tax_line.move_line == move_line.id)
            .join(move, condition=move_line.move == move.id)
            .join(tax, condition=tax_line.tax == tax.id)
            .select(tax_line.tax.as_('tax'),
                *columns,
                where=tax_line.tax.in_(tax_ids)
                & (move_line.state != 'draft')
                & where
                & where_tax,
                group_by=tax_line.tax)
            )

        cursor.execute(*query)
        for row in cursor_dict(cursor):
            for name in names:
                value = row[name] or 0
                if not isinstance(value, Decimal):
                    value = Decimal(str(value))
                result[name][row['tax']] = value
        return result

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

    @classmethod
    def _amount_where_tax(cls, tax_line, move_line, move, tax):
        context = Transaction().context
        sourcing = context.get('sourcing')
        rate_type = context.get('rate_type')

        where = Literal(True)
        if sourcing:
            where = where & (tax.sourcing == sourcing)

        if rate_type:
            where = where & (tax.rate_type == rate_type)

        return where



class TaxCodeContext(metaclass=PoolMeta):
    __name__ = 'account.tax.code.context'

    sourcing = fields.Selection([
        (None, ""),
        ('intrastate', "In-state Destination"),
        ('interstate', "Out-of-state Destination"),
        ('origin', "Origin"),
        ], "Sourcing", sort=False)

    rate_type = fields.Selection([
        (None, ""),
        ('general', "General Rate"),
        ('food', "Food & Drug Rate"),
        ], "Rate Type", sort=False)


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
    place = fields.Many2One('census.place', "Related Place")

    @classmethod
    def copy(cls, rules, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('authority', None)
        return super().copy(rules, default=default)

