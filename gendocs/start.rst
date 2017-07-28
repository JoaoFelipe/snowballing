Getting started
---------------

To install the tool, you should follow these instructions:

-  First, install the python package:
-  ``$ pip install snowballing``

-  Then, download and install the latest
   `geckodriver <https://github.com/mozilla/geckodriver/releases>`__
-  In my case, I put the 'geckodriver.exe' file in the Firefox directory
   (``C:\Program Files (x86)\Mozilla Firefox``)
-  And I add the directory to the PATH environment variable

-  If you want to export the snowballing history (provenance), you must
   also install the following tools
-  `provtoolbox <http://lucmoreau.github.io/ProvToolbox/>`__
-  `GraphViz <http://www.graphviz.org/>`__

For starting a new literature review project, please run:

.. code:: bash

    $ snowballing start literature

This command will create a directory called ``literature`` (you are free
to use other name in the command) with the notebooks for performing the
snowballing and analyzing it, and an example database.

Inside the directory, start Jupyter:

.. code:: bash

    $ cd literature
    $ jupyter notebook

And open the file `Index.ipynb <example/Index.ipynb>`__. This file
contains all the instructions for understanding the database and
performing the snowballing.