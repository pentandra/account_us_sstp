=============================
Account US SSTP Scenario Sale
=============================

Testing the basic functionality of the module from a sale to the creation of an
invoice. Three types of boundary records will be tested: Zip, ZipPlus4, and
Address. Product Categories will carry a generic tax that should be converted
to a real tax. For simplicity, this test will use a *Tax Rule* without a group;
normally taxes will belong to a group when you are using them (and you will
have more than one tax to deal with). The scenario will use a target tax with a
reporting code and one without to test both possibilities in tax reporting.

See :doc:`this scenario <account_us_sstp_default_taxes>` for default taxes.

.. TODO: introduce another set of tax codes that do not use a reporting code?

.. _setup:

Setup
=====

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, create_tax, create_tax_code, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(['account_us_sstp', 'sale'])

Create authority::

    >>> Country = Model.get('country.country')
    >>> Subdivision = Model.get('country.subdivision')
    >>> us = Country(name="United States", code='US')
    >>> us.save()
    >>> authority = Subdivision(name="State", code='US-ST', country=us)
    >>> authority.type = 'state'
    >>> authority.save()

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> company_address, = company.party.addresses
    >>> company_address.country = us
    >>> company_address.subdivision = authority
    >>> company_address.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company, today))
    >>> fiscalyear.click('create_period')
    >>> period_ids = [p.id for p in fiscalyear.periods]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create taxes::

    >>> Tax = Model.get('account.tax')
    >>> generic_tax = Tax()
    >>> generic_tax.name = 'Generic tax'
    >>> generic_tax.description = generic_tax.name
    >>> generic_tax.type = 'none'
    >>> generic_tax.product_class = 'general'
    >>> generic_tax.save()

    >>> generic_food_tax, = generic_tax.duplicate()
    >>> generic_food_tax.product_class = 'food'
    >>> generic_food_tax.save()

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.code = 'bar'
    >>> tax.sourcing = 'intrastate'
    >>> tax.product_class = 'general'
    >>> tax.save()

    >>> food_tax = create_tax(Decimal('.025'))
    >>> food_tax.code = 'foo'
    >>> food_tax.sourcing = 'intrastate'
    >>> food_tax.product_class = 'food'
    >>> food_tax.save()

Create tax codes::

    >>> base_code = create_tax_code(tax, 'base', 'invoice')
    >>> line = base_code.lines.new()
    >>> line.authority = authority
    >>> line.operator = '+'
    >>> line.tax = food_tax
    >>> line.amount = 'base'
    >>> line.type = 'invoice'
    >>> base_code.save()
    >>> tax_code = create_tax_code(tax, 'tax', 'invoice')
    >>> tax_code.authority = authority
    >>> tax_code.code = 'foo'
    >>> line = tax_code.lines.new()
    >>> line.authority = authority
    >>> line.operator = '+'
    >>> line.tax = food_tax
    >>> line.amount = 'tax'
    >>> line.type = 'invoice'
    >>> tax_code.save()

Create tax rule::

    >>> TaxRule = Model.get('account.tax.rule')
    >>> rule = TaxRule(authority=authority)
    >>> rule.name  = "Tax Rule"
    >>> rule_line = rule.lines.new()
    >>> rule_line.authority = authority
    >>> rule_line.from_country = us
    >>> rule_line.from_subdivision = authority
    >>> rule_line.to_country = us
    >>> rule_line.to_subdivision = authority
    >>> rule_line.origin_tax = generic_tax
    >>> rule_line.tax = tax
    >>> rule_line = rule.lines.new()
    >>> rule_line.authority = authority
    >>> rule_line.from_country = us
    >>> rule_line.from_subdivision = authority
    >>> rule_line.to_country = us
    >>> rule_line.to_subdivision = authority
    >>> rule_line.origin_tax = generic_food_tax
    >>> rule_line.tax = food_tax
    >>> rule.save()

Create tax boundaries::

    >>> TaxBoundary = Model.get('account.tax.boundary')
    >>> TaxKey = Model.get('account.tax.boundary.tax_key')
    >>> tax_key = TaxKey(authority=authority)
    >>> tax_key.value = 'foo-bar'
    >>> tax_key.save()
    >>> boundary = TaxBoundary(authority=authority)
    >>> boundary.tax_key = tax_key
    >>> boundary.start_date = today
    >>> boundary.end_date = today
    >>> boundary.type = '4'
    >>> boundary.zipcode_low = '50000'
    >>> boundary.zipcode_high = '60000'
    >>> boundary.zipext_low = '3000'
    >>> boundary.zipext_high = '4000'
    >>> boundary.save()
    >>> boundary = TaxBoundary(authority=authority)
    >>> boundary.tax_key = tax_key
    >>> boundary.start_date = today
    >>> boundary.end_date = today
    >>> boundary.type = 'Z'
    >>> boundary.zipcode_low = '80000'
    >>> boundary.zipcode_high = '85000'
    >>> boundary.code = tax_code
    >>> boundary.save()
    >>> boundary = TaxBoundary(authority=authority)
    >>> boundary.tax_key = tax_key
    >>> boundary.start_date = today
    >>> boundary.end_date = today
    >>> boundary.type = 'A'
    >>> boundary.address_low = '100'
    >>> boundary.address_high = '300'
    >>> boundary.address_parity = 'E'
    >>> boundary.street = '12TH'
    >>> boundary.street_suffix = 'AVE'
    >>> boundary.city = 'Anytown'
    >>> boundary.zipcode = '12345'
    >>> boundary.zipext = '6789'
    >>> boundary.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer1 = Party(name='Customer 1')
    >>> customer1.customer_tax_rule = rule
    >>> address, = customer1.addresses
    >>> address.country = us
    >>> address.subdivision = authority
    >>> address.postal_code = '12345-6789'
    >>> address.city = 'Anytown'
    >>> address.street = '234 12th Ave'
    >>> customer1.save()

    >>> customer2 = Party(name='Customer 2')
    >>> customer2.customer_tax_rule = rule
    >>> address, = customer2.addresses
    >>> address.country = us
    >>> address.subdivision = authority
    >>> address.postal_code = '82345'
    >>> address.city = 'Anytown'
    >>> address.street = '1234 East St.'
    >>> customer2.save()

    >>> customer3 = Party(name='Customer 3')
    >>> customer3.customer_tax_rule = rule
    >>> address, = customer3.addresses
    >>> address.country = us
    >>> address.subdivision = authority
    >>> address.postal_code = '55555-4000'
    >>> address.city = 'Trytown'
    >>> address.street = 'PO Box 4000'
    >>> customer3.save()

    >>> customer4 = Party(name='Customer 4')
    >>> customer4.customer_tax_rule = rule
    >>> address, = customer4.addresses
    >>> address.country = us
    >>> address.subdivision = authority
    >>> address.postal_code = '55555-4001'
    >>> address.city = 'Trytown'
    >>> address.street = 'PO Box 4001'
    >>> customer4.save()

    >>> customer5 = Party(name='Customer 5')
    >>> address, = customer5.addresses
    >>> address.country = us
    >>> address.subdivision = authority
    >>> address.postal_code = '55555-4000'
    >>> address.city = 'Trytown'
    >>> address.street = 'PO Box 4000'
    >>> customer5.save()

Create account categories::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

    >>> account_category_tax, = account_category.duplicate()
    >>> account_category_tax.customer_taxes.append(generic_tax)
    >>> account_category_tax.save()

    >>> account_category_tax_food, = account_category.duplicate()
    >>> account_category_tax_food.customer_taxes.append(generic_food_tax)
    >>> account_category_tax_food.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category_tax
    >>> template.save()
    >>> product, = template.products

    >>> template_food, = template.duplicate()
    >>> template_food.account_category = account_category_tax_food
    >>> template_food.save()
    >>> food, = template_food.products

Add address to default warehouse::

    >>> Location = Model.get('stock.location')
    >>> warehouse, = Location.find([('code', '=', 'WH')])
    >>> warehouse.address = company_address
    >>> warehouse.save()

.. _Customer 1 tests:

Customer 1 Tests ('A' boundary resolution)
==========================================

Create sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale(party=customer1)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 10.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'pending'
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> line_tax, = invoice_line.taxes
    >>> assertEqual(line_tax, tax)
    >>> invoice.total_amount
    Decimal('110.00')

Create food sale::

    >>> sale = Sale(party=customer1)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = food
    >>> sale_line.quantity = 10.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check food invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'pending'
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> line_tax, = invoice_line.taxes
    >>> assertEqual(line_tax, food_tax)
    >>> invoice.total_amount
    Decimal('102.50')

.. _Customer 2 tests:

Customer 2 Tests ('Z' boundary resolution)
==========================================

For no other reason than that the ZIP Code search is simplest, I'm testing the
``foo`` tax code logic in this section. Notice that the matching boundary
record was the only one set with a tax code as part of the :ref:`setup`.

Create sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale(party=customer2)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'pending'
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> line_tax, = invoice_line.taxes
    >>> assertEqual(line_tax, tax)
    >>> invoice.total_amount
    Decimal('55.00')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

    >>> move = invoice.move
    >>> move.state
    'posted'
    >>> move_line, = [l for l in move.lines if l.account == accounts['tax']]
    >>> tax_line, = move_line.tax_lines
    >>> assertEqual(tax_line.code, 'foo')

Create food sale::

    >>> sale = Sale(party=customer2)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = food
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check food invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'pending'
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> line_tax, = invoice_line.taxes
    >>> assertEqual(line_tax, food_tax)
    >>> invoice.total_amount
    Decimal('51.25')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

    >>> move = invoice.move
    >>> move.state
    'posted'
    >>> move_line, = [l for l in move.lines if l.account == accounts['tax']]
    >>> tax_line, = move_line.tax_lines
    >>> assertEqual(tax_line.code, 'foo')

Check tax codes::

    >>> TaxCode = Model.get('account.tax.code')
    >>> with config.set_context(periods=period_ids):
    ...     base_code = TaxCode(base_code.id)
    ...     tax_code = TaxCode(tax_code.id)
    >>> base_code.amount
    Decimal('100.00')
    >>> tax_code.amount
    Decimal('6.25')
    >>> with config.set_context(periods=period_ids, product_class='general'):
    ...     base_code = TaxCode(base_code.id)
    ...     tax_code = TaxCode(tax_code.id)
    >>> base_code.amount
    Decimal('50.00')
    >>> tax_code.amount
    Decimal('5.00')
    >>> with config.set_context(periods=period_ids, product_class='food'):
    ...     base_code = TaxCode(base_code.id)
    ...     tax_code = TaxCode(tax_code.id)
    >>> base_code.amount
    Decimal('50.00')
    >>> tax_code.amount
    Decimal('1.25')
    >>> with config.set_context(periods=period_ids, sourcing='intrastate'):
    ...     base_code = TaxCode(base_code.id)
    ...     tax_code = TaxCode(tax_code.id)
    >>> base_code.amount
    Decimal('100.00')
    >>> tax_code.amount
    Decimal('6.25')
    >>> with config.set_context(periods=period_ids, sourcing='interstate'):
    ...     base_code = TaxCode(base_code.id)
    ...     tax_code = TaxCode(tax_code.id)
    >>> base_code.amount
    Decimal('0.00')
    >>> tax_code.amount
    Decimal('0.00')

.. _Customer 3 tests:

Customer 3 Tests ('4' boundary resolution)
==========================================

Create sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale(party=customer3)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 10.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'pending'
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> line_tax, = invoice_line.taxes
    >>> assertEqual(line_tax, tax)
    >>> invoice.total_amount
    Decimal('110.00')

Create food sale::

    >>> sale = Sale(party=customer3)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = food
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check food invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'pending'
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> line_tax, = invoice_line.taxes
    >>> assertEqual(line_tax, food_tax)
    >>> invoice.total_amount
    Decimal('51.25')

.. _Customer 4 tests:

Customer 4 Tests ('4' boundary not resolved)
============================================

Create sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale(party=customer4)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 10.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'pending'
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> line_tax, = invoice_line.taxes
    >>> assertEqual(line_tax, generic_tax)
    >>> invoice.total_amount
    Decimal('100.00')

Create food sale::

    >>> sale = Sale(party=customer4)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = food
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check food invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'pending'
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> line_tax, = invoice_line.taxes
    >>> assertEqual(line_tax, generic_food_tax)
    >>> invoice.total_amount
    Decimal('50.00')

.. _Customer 5 tests:

Customer 5 Tests (party without tax rule, tax not resolved)
===========================================================

Create sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale(party=customer5)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 10.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'pending'
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> line_tax, = invoice_line.taxes
    >>> assertEqual(line_tax, generic_tax)
    >>> invoice.total_amount
    Decimal('100.00')

Create food sale::

    >>> sale = Sale(party=customer5)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = food
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check food invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'pending'
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> line_tax, = invoice_line.taxes
    >>> assertEqual(line_tax, generic_food_tax)
    >>> invoice.total_amount
    Decimal('50.00')
