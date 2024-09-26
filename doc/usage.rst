*****
Usage
*****

.. warning::

   This module is currently not a complete solution for sales taxes for the
   entire United States, but it may be a complete solution for sales taxes for
   some companies. See states that are `currently supported`_.

.. _currently supported: https://www.streamlinedsalestax.org/Shared-Pages/State-Detail

.. _setting the customer tax rule:

Setting the customer tax rule
=============================

Once the tax rates and boundaries have been imported using the :doc:`provided
scripts <setup>`, here are a couple tips for a smooth operation:

1. Before making a `Sale <sale:model-sale.sale>` be sure a *Customer Tax Rule*
   is set for the `Party <party:model-party.party>` of the sale.

.. tip::

   If you set a *Default Customer Tax Rule* in [:menuselection:`Account
   Configuration`] to the tax rule for your state, this will automatically set
   the customer tax rule to this value when creating new parties. This is
   helpful if you do most of your business in one state.

.. seealso::

   Parties can be found by opening the main menu item:

      |Parties --> Parties|__

      .. |Parties --> Parties| replace:: :menuselection:`Parties --> Parties`
      __ https://demo.tryton.org/model/party.party


.. seealso::

   Account configuration settings are found by opening the main menu item:

      |Financial --> Configuration --> Configuration|__

      .. |Financial --> Configuration --> Configuration| replace:: :menuselection:`Financial --> Configuration --> Configuration`
      __ https://demo.tryton.org/model/account.configuration/1

2. In order to determine the correct destination taxes, both the *Shipping
   Address* of the *Party* and a *Warehouse* (with an address from whence the
   goods will be shipped) need to be present on the `Sale
   <sale:model-sale.sale>` form before adding sale lines.

.. note::

   This requirement actually comes from the :doc:`Account Tax Rule Country
   Module <account_tax_rule_country:index>`.

.. seealso::

   Sales are found by opening the main menu item:

      |Sales --> Sales|__

      .. |Sales --> Sales| replace:: :menuselection:`Sales --> Sales`
      __ https://demo.tryton.org/model/sale.sale


.. _Viewing your tax code data:

Viewing your tax code data
==========================

Opening the [:menuselection:`Financial --> Reporting --> Chart of Tax Codes`]
reveals two additional parameters from the Streamlined Sales Tax data:
*Sourcing* and *Product Class*. You can adjust these to filter the types of
taxes that are used for your tax reporting.
