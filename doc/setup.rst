*****
Setup
*****

When the ``account_us_sstp`` module is activated it does not create any tax,
tax rule, tax code, or tax boundary records. You do this using the provided
scripts.

.. important::

   Before running these scripts, you must run the ``trytond_import_countries``
   script from the :doc:`Country Module <country:index>` to populate the
   records needed to associate this module’s models with a state tax authority.

   Optionally, you may run the ``trytond_import_uscensus_subdivisions`` script
   from the :doc:`Country US Census Module <country_uscensus:index>` in order
   to populate smaller `Subdivision <country:model-country.subdivision>`
   records, including records for counties, cities, towns, and other physical
   places. These records are needed when importing the rates in order to
   associate `Taxes <model-account.tax>` with a physical place and enabling
   human-oriented descriptions of taxes that include place names.

It is possible to import tax data for a select number of states, for example,
for those in which you are collecting tax or in which your business has
achieved a tax nexus. This will allow you to carefully manage the size of the
database and scope of the business.

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

.. warning::

   This process may take awhile, depending on the state.

It is run with:

.. code-block:: sh

   trytond_import_boundaries -c trytond.conf -d <database> <two_letter_country_code>

.. tip::

   To reduce the size of your database backups (and since the boundary records
   are considered ephemeral data that can be re-imported at will), consider
   using ``--exclude-table-data='account_tax_boundary'`` in your backup script.

   See https://www.postgresql.org/docs/current/app-pgdump.html for more info.
