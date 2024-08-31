*****
Setup
*****

When the ``account_us_sstp`` module is activated it does not create any tax, tax
rule, or tax code records. You do this using the provided scripts.

Before running these scripts, you must run the scripts from the
`country_uscensus` module to populate the `Place <model-census.place>` records.
It is possible to import tax data only for those states for which you are
collecting or in which your business has achieved a tax nexus. This will allow
you to keep the size of the database as small as possible, if desired.

.. _Loading and updating tax rates:

Loading and updating tax rates
==============================

The :command:`trytond_import_rates` script loads and updates Tryton with the
`Taxes <model-account.tax>` for the given states.

You run it with:

.. code-block:: sh

   trytond_import_rates -c trytond.conf -d <database> <two_letter_state_code>

.. _Loading and updating boundary records:

Loading and updating boundary records
=====================================

You can use the :command:`trytond_import_boundaries` script to load Tryton with
the `Tax Boundary <model-account.tax.boundary>` records for the given states.
`Tax Rules <model-account.tax.rule>` and `Tax Codes <model-account.tax.code>`
associated with the imported boundaries will be loaded and updated as well.

   :: warning:
     
     This process may take awhile, depending on the state.

It is run with:

.. code-block:: bash

   trytond_import_boundaries -c trytond.conf -d <database> <two_letter_country_code>
