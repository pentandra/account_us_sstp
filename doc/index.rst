######################
Account US SSTP Module
######################

The `Tryton`_ ``account_us_sstp`` module adds tax accounting for member states
of the `Streamlined Sales Tax Project`_ (SSTP), a destination-based
sales-and-use tax approach for the United States.

You can use the tax data without being registered through the `Streamlined
Sales Tax Registration System`_ (SSTRS) or being in compliance with the
Streamlined Sales and Use Tax Agreement (SSUTA).

Why use this when I can use a Certified Service Provider (CSP), possibly for
free? First of all, I think it is silly to have to rely on the Internet and a
third-party tax information provider to complete a business transaction or even
give a quote, not to mention any security or privacy concerns of giving a
third-party transactional and product information about your business. Second,
it may be that not all states compensate CSPs, and depending upon your sales
volume, this may be a cheaper solution in the long or even short run—or at
least an alternative to consider. Third, this module builds upon Tryton's
existing tax models, including tax rules and reporting. Fourth, it is hoped
that this project can make more people aware of the Streamlined Sales Tax
Project, which seems to be a viable model for taxes in the United States (as
far as taxes go). The hope is to encourage those states that are not yet on
board, to get on board, or in some way make their tax data available to the
public in open formats.

This module currently supports dynamic lookup of taxes for Sales, Purchases and
Invoices based on transaction date and customer destination address. Submission
of tax returns electronically is on the table, but is not yet supported.

.. _Tryton: https://www.tryton.org/

.. _Streamlined Sales Tax Project: https://www.streamlinedsalestax.org/

.. _Streamlined Sales Tax Registration System: https://www.sstregister.org/

.. toctree:: :maxdepth: 2

   setup
   usage
   design
   reference
   releases
