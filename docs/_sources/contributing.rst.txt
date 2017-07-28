Contributing
===============

Feel free to contribute to the project!

For installing in development mode, clone the repository and use
``pip install -e``:

.. code:: bash

    $ git clone git@github.com:JoaoFelipe/snowballing.git
    $ cd snowballing
    $ pip install -e snowballing

Notes
-----

This project started as part of a literature snowballing. The tools were
developped out of necessity in a adhoc way. Thus, it has some bad design
decisions, such as using Python scripts as a database, and choosing
field names that are far from ideal.

Contributions to fix these and other issues are welcome! If you are
going to change a field name that is used by the tool, please, try to
make it configurable.