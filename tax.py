from trytond.model import (
        DeactivableMixin, MatchMixin, ModelSQL, ModelView, fields,
        sequence_ordered, tree)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

JURISDICTION_TYPES = [
        ('00', 'County'),
        ('01', 'City'),
        ('02', 'Town'),
        ('03', 'Village'),
        ('04', 'Borough'),
        ('05', 'Township'),
        ('09', 'Other Municipality'),
        ('10', 'School District'),
        ('11', 'Junior Colleges'),
        ('19', 'Other Schools'),
        ('20', 'Water Control'),
        ('21', 'Utility District'),
        ('22', 'Sanitation'),
        ('23', 'Water or Sewer District'),
        ('24', 'Reclamation District'),
        ('25', 'Fire or Police'),
        ('26', 'Roads or Bridges'),
        ('27', 'Hospitals'),
        ('29', 'Other Municipal Services'),
        ('40', 'Township and County'),
        ('41', 'City and School'),
        ('42', 'County collected by Other Taxing Authority'),
        ('43', 'State and County'),
        ('44', 'Central Collection Taxing Authority'),
        ('45', 'State Taxing Authority'),
        ('49', 'Other Combination Collection'),
        ('50', 'Bond Authority'),
        ('51', 'Annual County Bond Authority'),
        ('52', 'Semi-annual County Bond Authority'),
        ('53', 'Annual City Bond Authority'),
        ('54', 'Semi-annual City Bond Authority'),
        ('59', 'Other Bond Authority'),
        ('61', 'Assessment District'),
        ('62', 'Homeowner\'s Association'),
        ('63', 'Special District'),
        ('69', 'Other Special Districts'),
        ('70', 'Central Appraisal Taxing Authority'),
        ('71', 'Unsecured County Taxes'),
        ('72', 'Mobile Home Authority'),
        ('79', 'Other Special Applications'),
        ]

class Jurisdiction(DeactivableMixin, ModelSQL, ModelView):
    "Tax Jurisdiction"
    __name__ = 'account.tax.jurisdiction'
    code = fields.Char("Code", required=True,
        help="The code of the jurisdiction.")
    name = fields.Char("Name")
    authority = fields.Many2One('census.place', "Authority",
        domain=[('parent', '=', None)],
        help="The entity in charge of this tax jurisdiction")
    place = fields.Many2One(
        'census.place', "Place",
        domain=[
            #('authority', '=', Eval('authority', -1))
            ],
        help="The place associated with the jurisdiction.")
    type = fields.Selection(JURISDICTION_TYPES, "Type")
    taxes = fields.One2Many(
            'account.tax', 'jurisdiction', "Taxes", readonly=True)
    
    @fields.depends('code', 'name', 'place', 'authority')
    def on_change_place(self):
        if self.place:
            if not self.code:
                self.code = self.place.code_fips
            if not self.name:
                self.name = self.place.name
            if not self.authority:
                #TODO: move to Place class?
                authority = self.place
                while authority.parent != None:
                    authority = authority.parent
                self.authority = authority


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'
    jurisdiction = fields.Many2One(
            'account.tax.jurisdiction', "Jurisdiction", ondelete='CASCADE')
