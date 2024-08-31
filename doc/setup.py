*****
Setup
*****

When the ``account_us_sstp`` module is activated it does not create any tax, tax
rule, or tax code records. You do this using the provided scripts.

   :: note:

     Before running these scripts, you must run the scripts from the
     ``country`` and ``country_uscensus`` modules to populate the `Country
     <model-country.country>`, `Subdivision <model-country.subdivision>`, and
     `Place <model-census.place>` records. These are needed to associate `Taxes
     <model-account.tax>` and `Tax Rules <model-account.tax.rule>` with a state
     tax authority and, for convenience, a physical location.

It is possible to import tax data for a select number of states, for example,
for those in which you are collecting tax or in which your business has
achieved a tax nexus. This will allow you to keep the size of the database as
small as possible.

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

Once you have loaded the rates for a state, you use the
:command:`trytond_import_boundaries` script to load Tryton with the `Tax
Boundary <model-account.tax.boundary>` records for that state. `Tax Rules
<model-account.tax.rule>` and `Tax Codes <model-account.tax.code>` associated
with the imported boundaries will be loaded and updated as well.

   :: warning:
     
     This process may take awhile, depending on the state.

It is run with:

.. code-block:: bash

   trytond_import_boundaries -c trytond.conf -d <database> <two_letter_country_code>
