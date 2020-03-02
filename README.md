John Snow / Snowballing
==========

This project provides tools for perfoming a liberature review through snowballing. It includes a Chrome plugin that assists the forward step of literature snowballing, Jupyter Notebook widgets that assist the backward and forward steps of literature snowballing, notebooks that assist in inserting citations in the database, and notebooks for analyzing the snowballing and producing citation graphs, publication place histograms, and a summarization of the snowballing steps.

This package was tested on Python 3.6 using Windows and Python 3.7 using Linux, but it should support Python > 3.5 in any operating system. Please, open an issue if it is not the case.

Please, find the project documentation at [https://joaofelipe.github.io/snowballing](https://joaofelipe.github.io/snowballing)

Getting started
------------------

To install the tool, you should run:

`$ pip install snowballing `

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

Supporting tools
------------------

This tool uses other tools that require external installations to assist in the literature review. You may or may not need them all. In this section, we present these tools and describe how to install them.

### John Snow Chrome Plugin

This plugin modifies the Google Scholar search page to include "BibTex", "Work", and "Add" buttons to assist in adding papers to the tool. It is specially helpful in the forward step of the snowballing, as it allows uses to configure a "citation_var", click on the "cited by" and add work with their citations.

To install it:
  - Use the following command to generate a folder with the Chrome plugin:
    - `$ snowballing plugin`
  - Activate the developer mode in Chrome and click in "Load unpacked" to load the plugin from the generated folder.

To run it:
  - Go to the snowballing project folder
  - Start the plugin server:
    - `$ snowballing web`
  - Load a Google Scholar page
  - Note that if you click on the plugin icon, it now shows configuration options


### Selenium Webdriver

Three notebooks use Selenium to search google scholar:
- SearchScholar.ipynb : Use a search string to search work from scholar and add it using the tool
- Forward.ipynb : Perform forward snowballing using the Scholar "cited by" link
- Validate.ipynb : Validate dabatase items by searching each item at Google Scholar and comparing their BibTex.

While I recommend to use the Chrome Plugin for the former two (Google is less lenient to the Selenium method, since it performs many requests at the same time), it is hard to escape from Selenium in the third method. Hence, I suggest to install and configure a WebDriver.

I have tested the tool with both the [geckodriver](https://github.com/mozilla/geckodriver/releases) (for Firefox) and the [ChromeDriver](https://chromedriver.chromium.org/) (for Chrome).

To install it:
  - Install the desired WebDriver and Browser
  - Add it to the PATH environment variable
  - Configure variable `config.WEB_DRIVER` in your `database/__init__.py` to indicate the proper WebDriver


### Text Editor

Some text editors support command line arguments to open files on specific lines. We use these commands both on the Chrome Plugin and on the Validate.ipynb notebook to jump to Work definitions in year files stored at `database/work`. Please, consider installing a text editor that support this feature and configuring it accordingly.

For [Visual Studio Code](https://code.visualstudio.com/), configure the variable `config.LINE_PARAMS` in your `database/__init__.py` to `"--goto {year_path}:{line}"`

For [Sublime Text](https://www.sublimetext.com/), configure the variable `config.LINE_PARAMS` in your `database/__init__.py` to `"{year_path}:{line}"`


### GraphViz

We use [GraphViz](http://www.graphviz.org/) to generate the snowballing history (provenance) in the notebook SnowballingProvenance.ipynb. Please, consider installing it.


### ProvToolBox

We also use [provtoolbox](http://lucmoreau.github.io/ProvToolbox/) to visualize the snowballing provenance in the notebook SnowballingProvenance.ipynb. It is more verbose than the other visualization format, but if you prefer to visualize it in a provenance format, consider installing it as well.


Contributing
----------------

Feel free to contribute to the project!

For installing in development mode, clone the repository and use `pip install -e`:
```bash
$ git clone git@github.com:JoaoFelipe/snowballing.git
$ cd snowballing
$ pip install -e snowballing
```

For testing it:
```bash
$ cd snowballing
$ python test.py
```

Known Usages
-------------

This tools has been used to support two papers:

- Pimentel, J. F., Freire, J., Murta, L., & Braganholo, V. (2019). A survey on collecting, managing, and analyzing provenance from scripts. ACM Computing Surveys (CSUR), 52(3), 1-38.
  Material: https://dew-uff.github.io/scripts-provenance

- Mourão. E., Pimentel, J. F.,  Murta, L., Kalinowski, M., Mendes, E., Wohlin, C. (2020 in press). On the Performance of Hybrid Search Strategies for Systematic Literature Reviews in Software Engineering. Information and Software Technology (IST).
  Material: https://gems-uff.github.io/hybrid-strategies


It also has been used to calculate the h-index of a conference: https://github.com/JoaoFelipe/ipaw-index


Notes
----

This project started as part of a literature snowballing. The tools were developped out of necessity in a adhoc way. Thus, it has some bad design decisions, such as using Python scripts as a database.

Contributions to fix issues and bug reports are welcome!


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

