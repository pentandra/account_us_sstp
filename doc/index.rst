#####################
Account US Tax Module
#####################

The *Account US Tax module* adds tax accounting for member states of the
`Streamlined Sales Tax Project`_ (SSTP), a destination-based sales-and-use tax
approach for the United States. This module currently supports dynamic lookup
of taxes for Sales, Purchases and Invoices based on transaction date and
customer destination address. Submission of tax returns electronically is on
the table, but is not yet supported. Other states may be supported on an ad hoc
basis if their sales tax models are similar enough in approach to the SSTP.
Pull requests and/or financial contributions are welcome.

You can use the this module and tax data imported by the scripts without being
registered through the `Streamlined Sales Tax Registration System`_ (SSTRS) or
committed to the Streamlined Sales and Use Tax Agreement (SSUTA).

Why use this module when I can use a Certified Service Provider (CSP) (or some
other sales tax provider), possibly for free? *First of all*, I think it is
silly to have to rely on the Internet and a third-party tax information
provider to make a sales tax computation for even something as basic as a
quote, not to mention the security or privacy concerns of giving a third-party
transactional and product information about your business. *Second*, it may be
that not all states compensate CSPs, and depending upon your sales volume, this
may be a cheaper solution in the long or even short run—or at least an
alternative to consider. *Third*, this module builds upon Tryton's existing tax
models, including tax rules and reporting, so it should be compatible with tax
modules from other countries. *Fourth*, it is hoped that this project can make
more people aware of the Streamlined Sales Tax Project, which seems to be a
sensible model for taxes in the United States (as far as sales taxes are
sensible). The hope is to encourage those states that are not yet on board, to
get on board, or in some way make their tax data available to the public in
open formats.

==================== ======== =====  ========== =============
       State          Method  Rates  Boundaries Tax Structure
==================== ======== =====  ========== =============
Alabama
Alaska
Arizona
Arkansas               SSTP    CSV
California
Colorado                                        State tax plus optional "home rule" county and local jurisdictions
Connecticut
Delaware
District of Columbia
Florida
Georgia                SSTP    CSV
Hawaii
Idaho
Illinois
Indiana                SSTP    CSV
Iowa                   SSTP    CSV
Kansas                 SSTP    CSV
Kentucky               SSTP    CSV
Louisiana
Maine
Maryland
Massachusetts
Michigan               SSTP    CSV
Minnesota              SSTP    CSV
Mississippi
Missouri
Montana
Nebraska               SSTP    CSV
Nevada                 SSTP    CSV
New Hampshire
New Jersey             SSTP    CSV
New Mexico
New York
North Carolina         SSTP    CSV
North Dakota           SSTP    CSV
Ohio                   SSTP    CSV
Oklahoma               SSTP    CSV
Oregon
Pennsylvania
Puerto Rico
Rhode Island           SSTP    CSV
South Carolina
South Dakota           SSTP    CSV
Tennessee              SSTP    CSV
Texas
Utah                   SSTP    CSV
Vermont                SSTP    CSV
Virginia
Washington             SSTP    CSV
West Virginia          SSTP    CSV
Wisconsin              SSTP    CSV
Wyoming                SSTP    CSV

Other approaches
================

- https://github.com/openlabs/trytond-avalara

.. _Tryton: https://www.tryton.org/

.. _Streamlined Sales Tax Project: https://www.streamlinedsalestax.org/

.. _Streamlined Sales Tax Registration System: https://www.sstregister.org/

.. toctree::
   :maxdepth: 2

   setup
   usage
   design
   reference
   releases
