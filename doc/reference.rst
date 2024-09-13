*************
API Reference
*************

Tax Authority
=============

.. class:: TaxAuthorityMixin

   A tax authority is a `Subdivision <country:model-country.subdivision>` with
   no parent (i.e. a state—in the United States, sales and use taxes are a
   state's prerogative). This mixin_ makes it easy to create a
   :class:`~trytond:trytond.model.Model` for imported tax data that is used for
   reference rather than to be edited. As such, it makes most of the fields
   ``readonly``. It also limits any parent or child fields of the class to the
   same tax authority.

   Reminiscent of the ``account_template`` field of the `Account
   <account:model-account.account>` concept.

Tax Boundaries
==============

.. class:: BoundaryLocatorMixin

   Given an address and a date, this mixin_ provides a method to classes that
   inherit it that returns the most specific `Boundary
   <model-account.tax.boundary>` record available. Currently only supports
   addresses in the United States.

.. _mixin: https://en.wikipedia.org/wiki/Mixin
