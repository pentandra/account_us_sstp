from trytond.model import DeactivableMixin, ModelSQL, ModelView, fields, tree
from trytond.pyson import Eval
from trytond.tools import is_full_text, lstrip_wildcard

class Region(tree(), ModelSQL, ModelView):
    "Region"
    __name__ = 'census.region'

    name = fields.Char("Name", required=True, translate=True)
    code = fields.Char("Code", size=2,
            help="Region or division code of the census.")
    parent = fields.Many2One('census.region', "Parent")
    divisions = fields.One2Many('census.region', 'parent', "Divisions")
    places = fields.One2Many(
            'census.place', 'region', "Places",
            filter=[('parent', '=', None)],
            add_remove=[
                ('parent', '=', None),
                ('region', '=', None),
                ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('code', 'ASC'))

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = clause[2]
        if clause[1].endswith('like'):
            code_value = lstrip_wildcard(clause[2])
        return [bool_op,
            ('name',) + tuple(clause[1:]),
            ('code', clause[1], code_value) + tuple(clause[3:]),
            ]

class ClassCode(DeactivableMixin, ModelSQL, ModelView):
    "Class Code"
    __name__ = 'census.class_code'
    code = fields.Char("Code", size=2, required=True)
    description = fields.Char("Description", required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('code', 'ASC'))

    def get_rec_name(self, name):
        return '[%s] %s' % (self.code, self.description)

class Place(tree(), DeactivableMixin, ModelSQL, ModelView):
    "Place"
    __name__ = 'census.place'
    country = fields.Many2One(
            'country.country', "Country", required=True, ondelete='CASCADE',
            help="The country that contains the place geographically.")
    subdivision = fields.Many2One(
            'country.subdivision', "Subdivision", required=True, ondelete='CASCADE',
            domain=[('country', '=', Eval('country', -1))],
            help="The subdivision where the place is.")
    name = fields.Char("Name", required=True, translate=True)
    code_gnis = fields.Integer("Feature ID",
            help="The GNIS Feature ID of the geographical location.")
    code_fips = fields.Char("FIPS Code",
            help="The FIPS code (deprecated) of the geographical location.")
    class_code = fields.Many2One('census.class_code', "Class Code")
    level = fields.Function(fields.Char("Level"), 'on_change_with_level')
    region = fields.Many2One('census.region', "Region")
    parent = fields.Many2One('census.place', 'Parent',
            domain=[
                ('country', '=', Eval('country', -1)),
                ('subdivision', '=', Eval('subdivision', -1)),
                ],
            help="Add geographical place below the parent.")
    children = fields.One2Many('census.place', 'parent', "Places")


    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('subdivision', 'ASC'))
        cls._order.insert(1, ('code_fips', 'ASC'))

    @classmethod
    def default_level(cls):
        return 'unknown'

    @fields.depends('code_fips')
    def on_change_with_level(self, name=None):
        levels = { 
                2: 'state',
                3: 'county',
                5: 'place',
                }
        return levels.get(len(self.code_fips), 'unknown')

    def get_rec_name(self, name):
        if self.code_fips:
            return '%s (%s)' % (self.name, self.code_fips)
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = operand
        if operator.endswith('like') and is_full_text(operand):
            code_value = lstrip_wildcard(operand)
        return [bool_op,
            ('code_fips', operator, code_value, *extra),
            ('name', operator, operand, *extra),
            ]
