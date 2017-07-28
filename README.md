Snowballing
==========

This project provides tools for perfoming a liberature review through snowballing. It includes Jupyter Notebook widgets that assist the backward and forward steps of literature snowballing, notebooks that assist in inserting citations in the database, and notebooks for analyzing the snowballing and producing citation graphs, publication place histograms, and a summarization of the snowballing steps.

This package was tested on Python 3.6 using Windows, but it should support Python > 3.5 in any operating system. Please, open an issue if it is not the case.

Please, find the project documentation at [https://joaofelipe.github.io/snowballing](https://joaofelipe.github.io/snowballing)

Getting started
------------------

To install the tool, you should follow these instructions:

- First, install the python package:
  - `$ pip install snowballing `

- Then, download and install the latest [geckodriver](https://github.com/mozilla/geckodriver/releases)
  - In my case, I put the 'geckodriver.exe' file in the Firefox directory (`C:\Program Files (x86)\Mozilla Firefox`)
  - And I add the directory to the PATH environment variable
  
- If you want to export the snowballing history (provenance), you must also install the following tools
  - [provtoolbox](http://lucmoreau.github.io/ProvToolbox/)
  - [GraphViz](http://www.graphviz.org/)

For starting a new literature review project, please run:
```bash
$ snowballing start literature
```
This command will create a directory called `literature` (you are free to use other name in the command) with the notebooks for performing the snowballing and analyzing it, and an example database.


Inside the directory, start Jupyter:
```bash
$ cd literature
$ jupyter notebook
```

And open the file [Index.ipynb](example/Index.ipynb). This file contains all the instructions for understanding the database and performing the snowballing.

Contributing
----------------

Feel free to contribute to the project!

For installing in development mode, clone the repository and use `pip install -e`:
```bash
$ git clone git@github.com:JoaoFelipe/snowballing.git
$ cd snowballing
$ pip install -e snowballing
```

Notes
----

This project started as part of a literature snowballing. The tools were developped out of necessity in a adhoc way. Thus, it has some bad design decisions, such as using Python scripts as a database, and choosing field names that are far from ideal.

Contributions to fix these and other issues are welcome! If you are going to change a field name that is used by the tool, please, try to make it configurable.


Contact
----

Do not hesitate to contact me:

* João Felipe Pimentel <joaofelipenp@gmail.com>


License Terms
-------------

The MIT License (MIT)

Copyright (c) 2017 Joao Felipe Pimentel <joaofelipenp@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

