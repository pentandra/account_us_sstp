from decimal import Decimal

from sql import Literal, Null
from sql.aggregate import Sum
from sql.conditionals import Case

from trytond import backend
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.rpc import RPC
from trytond.tools import cursor_dict, is_full_text, lstrip_wildcard
from trytond.transaction import Transaction

PARITY = [
    (None, ""),
    ('O', 'Odd'),
    ('E', 'Even'),
    ('B', 'Both'),
    ]


class TaxAuthorityMixin:
    __slots__ = ()
    authority = fields.Many2One('country.subdivision', "Authority",
            domain=[
                ('country.code', '=', 'US'),
                ('parent', '=', None),
            ],
            help="The tax authority that administers this entity")
    authority_override = fields.Boolean('Override Definition',
            help="Check to override tax authority definition",
            states={
                'invisible': ~Bool(Eval('authority', -1)),
                })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        for fname in dir(cls):
            field = getattr(cls, fname)
            if ((isinstance(field, fields.Field)
                    and fname == 'authority_override')
                    or not isinstance(field, fields.Field)
                    or isinstance(field, fields.Function)):
                continue
            field.states['readonly'] = (
                Bool(Eval('authority', -1)) & ~Eval('authority_override',
                                                    False))

        if hasattr(cls, 'parent') and hasattr(cls, 'childs'):
            cls.parent.domain = [
                ('authority', '=', Eval('authority', -1)),
                cls.parent.domain or []]
            cls.parent.depends.update({'authority'})
            cls.childs.domain = [
                ('authority', '=', Eval('authority', -1)),
                cls.childs.domain or []]
            cls.childs.depends.update({'authority'})

    @classmethod
    def default_authority_override(cls):
        return False

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('authority', None)
        return super().copy(records, default=default)


class Tax(TaxAuthorityMixin, metaclass=PoolMeta):
    __name__ = 'account.tax'
    place = fields.Many2One('country.subdivision', "Related Place",
            states={
                'invisible': Bool(Eval('parent')),
                })
    code = fields.Char("Jurisdiction Code", size=5, states={
        'required': Bool(Eval('authority')),
        'invisible': ~Eval('authority') | Bool(Eval('parent')),
        })
    sourcing = fields.Selection([
        (None, ""),
        ('intrastate', "In-state Destination"),
        ('interstate', "Out-of-state Destination"),
        ('origin', "Origin"),
        ], "Sourcing", sort=False)
    product_class = fields.Selection([
        (None, ""),
        ('general', "General Goods & Services"),
        ('food', "Food & Drugs"),
        ], "Product Class", sort=False)

    def get_rec_name(self, name):
        parts = []
        if self.authority:
            parts.append(self.authority.code)
            parts.append(self.code)

        if self.place:
            parts.append(self.place.name)
        elif self.group:
            parts.append(self.group.name)
        else:
            parts.append("Special")

        if self.product_class:
            parts.append(self.product_class.capitalize())

        if self.sourcing == 'interstate':
            parts.append("Foreign")
        else:
            parts.append("Domestic")

        parts.append(self.name)
        return '—'.join(parts)

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not'):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = operand
        if operator.endswith('like') and is_full_text(operand):
            code_value = lstrip_wildcard(operand)
        return [bool_op,
            ('code', operator, code_value, *extra),
            (cls._rec_name, operator, operand, *extra),
            ]

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
            if backend.name == 'postgresql':  # FIXME
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
            return where & ((tax_line.code == code.code)
                            | (tax_line.code == Null))
        else:
            return where

    @classmethod
    def _amount_where_tax(cls, tax_line, move_line, move, tax):
        context = Transaction().context
        sourcing = context.get('sourcing')
        product_class = context.get('product_class')

        where = Literal(True)
        if sourcing:
            where = where & (tax.sourcing == sourcing)

        if product_class:
            where = where & (tax.product_class == product_class)

        return where

    @classmethod
    def copy(cls, taxes, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('code', None)
        return super().copy(taxes, default=default)


class TaxCodeContext(metaclass=PoolMeta):
    __name__ = 'account.tax.code.context'

    sourcing = fields.Selection([
        (None, ""),
        ('intrastate', "In-state Destination"),
        ('interstate', "Out-of-state Destination"),
        ('origin', "Origin"),
        ], "Sourcing", sort=False)

    product_class = fields.Selection([
        (None, ""),
        ('general', "General Goods & Services"),
        ('food', "Food & Drugs"),
        ], "Product Class", sort=False)


class TaxBoundary(TaxAuthorityMixin, ModelView, ModelSQL):
    "Tax Boundary"
    __name__ = 'account.tax.boundary'
    type = fields.Selection([
        ('A', 'Address'),
        ('Z', 'ZIP Code'),
        ('4', 'ZIP+4 Code'),
        ], "Boundary Type", required=True)
    start_date = fields.Date("Starting Date", required=True)
    end_date = fields.Date("End Date")
    address_low = fields.Char("Low Address Range", size=10, states={
        'required': Eval('type') == 'A',
        }, help="Low end of PO Box or street address numbers")
    address_high = fields.Char("High Address Range", size=10, states={
        'required': Eval('type') == 'A',
        }, help="High end of PO Box or street address numbers")
    address_parity = fields.Selection(PARITY, "Odd/Even Indicator",
        help="Indicates whether the given range of address(es) is "
        "odd or even. For PO Boxes this field should be blank.")
    street_pre = fields.Char("Street Predirectional", size=2)
    street = fields.Char("Street Name", size=20, states={
        'required': Eval('type') == 'A',
        })
    street_suffix = fields.Char("Street Suffix Abbreviation", size=4,
                help="Indicates the type of street")
    street_post = fields.Char("Street Postdirectional", size=2)
    secondary = fields.Char("Secondary Address Abbreviation", size=4)
    secondary_low = fields.Char("Address Secondary Low", size=8)
    secondary_high = fields.Char("Address Secondary High", size=8)
    secondary_parity = fields.Selection(PARITY, "Odd/Even Indicator")
    city = fields.Char("City Name", size=28, states={
        'required': Eval('type') == 'A',
        })
    zipcode = fields.Char("Zip Code", size=5, states={
        'required': Eval('type') == 'A',
        })
    zipext = fields.Char("ZIP+4", size=4, states={
        'required': Eval('type') == 'A',
        })
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
    company = fields.Many2One('company.company', "Company", required=True)
    rule = fields.Many2One('account.tax.rule', "Tax Rule",
            domain=[
                ('authority', '=', Eval('authority', -1)),
                ('company', '=', Eval('company', -1)),
                ],
            ondelete='RESTRICT', required=True)
    code = fields.Many2One('account.tax.code', "Tax Code",
            domain=[
                ('authority', '=', Eval('authority', -1)),
                ('company', '=', Eval('company', -1)),
                ],
            ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update(
            clean=RPC(
                readonly=False, fresh_session=True))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def clean(cls, domain=None):
        table = cls.__table__()
        cursor = Transaction().connection.cursor()
        if domain:
            query = cls.search(domain, query=True)
            where = table.id.in_(query)
        else:
            where = None
        cursor.execute(*table.delete(where=where))


class TaxCode(TaxAuthorityMixin, metaclass=PoolMeta):
    __name__ = 'account.tax.code'


class TaxCodeLine(metaclass=PoolMeta):
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
            [('code', '=', None)],
            ])

        context = Transaction().context
        sourcing = context.get('sourcing')
        product_class = context.get('product_class')

        if sourcing:
            domain.append([('tax.sourcing', '=', sourcing)])

        if product_class:
            domain.append([('tax.product_class', '=', product_class)])

        return domain


class TaxLine(metaclass=PoolMeta):
    __name__ = 'account.tax.line'
    code = fields.Char("Reporting Code")


class TaxRule(TaxAuthorityMixin, metaclass=PoolMeta):
    __name__ = 'account.tax.rule'

    place = fields.Many2One('country.subdivision', "Related Place")

    def get_rec_name(self, name):
        if self.place:
            return '%s [%s, %s]' % (self.name, self.place.name,
                                    self.place.code)
        else:
            return self.name
