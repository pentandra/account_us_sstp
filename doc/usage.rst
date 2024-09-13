*****
Usage
*****

.. warning::

   This module is currently not a complete solution for sales taxes for the
   entire United States, but it may be a complete solution for sales taxes for
   some companies. See states that are `currently supported`_.

.. _currently supported: https://www.streamlinedsalestax.org/Shared-Pages/State-Detail

.. _Dynamic resolution of taxes:

Dynamic resolution of taxes
===========================

For the most part, if you have run the :doc:`provided scripts <setup>` and
follow the Tryton `Sale <sale:model-sale.sale>` workflow, dynamic resolution of
taxes should just work for you. However, here are a couple tips for a smooth
operation:

1. If a *Customer Tax Rule* is set for a `Party <party:model-party.party>` or a
   *Default Customer Tax Rule* is set in [:menuselection:`Account
   Configuration`], this will override the dynamic resolution. The current
   design will only try to resolve a tax rule if these fields are not set.

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

2. In order to determine the correct taxes, the *Shipping Address* of the
   customer and a *Warehouse* (with an address) need to be entered into the
   `Sale <sale:model-sale.sale>` form before adding sale lines. This
   requirement actually comes from the :doc:`Account Tax Rule Country Module
   <account_tax_rule_country:index`.

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
