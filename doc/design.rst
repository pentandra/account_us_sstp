******
Design
******

.. seealso::

   The Streamlined Sales Tax `Technology Guide`_ for background information and
   technical requirements for this module.

.. _Technology Guide: https://www.streamlinedsalestax.org/docs/default-source/technology/technology-guide-october-2022.pdf

The *Account US SSTP Module* introduces or extends the following concepts:

.. _model-account.tax:

Tax
===

:abbr:`SSTP (Streamlined Sales Tax Project)` taxes are organized along two
axes: the destination source (*intrastate* or *interstate*) and the product
class (at the moment, two classes are used: *general* and *food/drug*).

A Tax can be related to a `physical location
<country:model-country.subdivision>` with the optional :doc:`Country US Census
Module <country_uscensus:index>`. This will provide human-readable descriptions
of the physical location related to each tax when the taxes are imported (if
the tax is associated with a physical location).

.. seealso::

   The `Tax <account:model-account.tax>` concept is introduced by the
   :doc:`Account Module <account:index>`.

.. _model-account.tax.boundary:

Tax Boundary
============

Using state-provided boundary records to provide the data, the appropriate `Tax
Key <model-account.tax.boundary.tax_key` and reporting code can be found using
the customer’s shipping address and transaction tax date. Boundary records come
in three types: Address, ZIP+4, and regular ZIP Code, in that priority order.

.. note::

   The tax boundary records are considered ephemeral. They are cleaned and
   imported periodically via script and no views are provided.

.. _model-account.tax.boundary.tax_key:

Tax Boundary Tax Key
====================

A composite key comprised of all applicable taxes of a boundary record.

.. _model-account.tax.code:

Tax Code
========

When the :doc:`import_boundaries script <setup>` is run, a tree of tax codes
for the given state is generated.

.. seealso::

   The `Tax Code <account:model-account.tax.code>` concept is introduced by the
   :doc:`Account Module <account:index>`.


.. _model-account.tax.code.line:

Tax Code Line
=============

When reporting, this model filters out any `Tax Lines <model-account.tax.line>`
that do not match its `Tax Code <model-account.tax.code>`.

.. seealso::

   The `Tax Code Line <account:model-account.tax.code.line>` concept is
   introduced by the :doc:`Account Module <account:index>`.

.. _model-account.tax.rule:

Tax Rule
========

Builds upon the logic from the :doc:`Account Tax Rule Country Module
<account_tax_rule_country:index>`, providing rules for taxes, both for
transactions within a state and between states.

One tax rule is created for each imported state.

.. seealso::

   The `Tax Rule <account:model-account.tax.rule>` concept is introduced by the
   :doc:`Account Module <account:index>`.

.. _model-account.tax.rule.line:

Tax Rule Line
=============

Matches rule line based on the components of a `Tax Key
<model-account.tax.boundary.tax_key>` made of all the applicable taxes.

.. _model-account.tax.line:

Tax Line
========

If a state uses composite :abbr:`SER (Simplified Electronic Return)` codes for
tax reporting, the code is stored on this model for later use.

.. seealso::

   The `TaxLine <account:model-account.tax.line>` concept is introduced by the
   :doc:`Account Module <account:index>`.

