******
Design
******

The *Account US SSTP Module* introduces or extends the following concepts:

.. _model-account.tax:

Tax
===

:abbr:`SSTP (Streamlined Sales Tax Project)` taxes are organized along two
axes: the destination source (*intrastate* or *interstate*) and the product
class (at the moment, two classes are used: *general* and *food/drug*).

A Tax can be related to a `physical location <country:Subdivision>`, but also
does not need to be.

.. seealso::

   The `Tax <account:model-account.tax>` concept is introduced by the
   :doc:`Account Module <account:index>`.

.. _model-account.tax.rule:

.. _model-account.tax.boundary:

Tax Boundary
============

This concept enables dynamic `Tax Rule <model-account.tax.rule>` resolution.
Using state-provided boundary records to provide the data, the appropriate rule
can be found using the customer’s shipping address and tax date.

.. note::

   The tax boundary records are considered ephemeral. They are cleaned and
   imported periodically via script and no views are provided.

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


.. _model-account.tax.line:

Tax Rule
========

Builds upon the logic from the :doc:`Account Tax Rule Country Module
<account_tax_rule_country:index>`, providing rules for taxes, both for
transactions within a state and between states.

A Tax Rule can be related to a `physical location <country:Subdivision>`, but
also does not need to be.

.. seealso::

   The `Tax Rule <account:model-account.tax.rule>` concept is introduced by the
   :doc:`Account Module <account:index>`.


.. _model-account.tax.code:

TaxLine
=======

If a state uses composite :abbr:`SER (Simplified Electronic Return)` codes for
tax reporting, the code is stored on this model for later use.

.. seealso::

   The `TaxLine <account:model-account.tax.line>` concept is introduced by the
   :doc:`Account Module <account:index>`.

