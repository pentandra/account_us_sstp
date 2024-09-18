====================================
US Streamlined Sales Tax Data Import
====================================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model
    >>> from trytond.modules.country_uscensus.scripts import (
    ...     import_uscensus_subdivisions,)
    >>> from trytond.modules.account_us_sstp.scripts import (
    ...     import_rates, import_boundaries)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts)
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(['country_uscensus', 'account_us_sstp'])

Import places::

    >>> Country = Model.get('country.country')
    >>> us = Country(name="United States", code='US')
    >>> us.save()

    >>> Subdivision = Model.get('country.subdivision')
    >>> ut = Subdivision(name="Utah", code='US-UT', country=us)
    >>> ut.save()

    >>> import_uscensus_subdivisions.do_import(['ut'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> payable = accounts['payable']

Import rates::

    >>> import_rates.do_import(['ut'], today, payable.name)

Import boundaries::

    >>> import_boundaries.do_import(['ut'], today)
