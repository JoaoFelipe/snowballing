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
$ snowballing start literature --profile bibtex
```
This command will create a directory called `literature` (you are free to use other name in the command) with the notebooks for performing the snowballing and analyzing it, and an example database. Note that the command specifies the profile `bibtex`, which is more user friendly. If you don't specify a profile, it will use the `default` profile (see below).


Inside the directory, start Jupyter:
```bash
$ cd literature
$ jupyter notebook
```

And open the file [Index.ipynb](example/Index.ipynb). This file contains all the instructions for understanding the database and performing the snowballing.


Profiles
----------

This tool is highly configurable through variables in the `config` module. These variables can be set using the `database/__init__.py` file. We consider each set of configurations a **profile**.

Currently, this tool supports starting the snowballing project using two profiles: `default` and `bibtex`.

### Default Profile

This tools started as part of a literature snowballing. The functions were developped out of necessity in a adhoc way. Thus, there are some bad design decisions.

One of these bad design decisions is the name of Work attributes. Some of them do not match well stablished BibTex fields. For instance:

- Work `name` refer to BibTex `title`

- Work `pp` refer to BibTex `pages`

- Work `authors` refer to BibTex `author`

Others have a bad names and direct translation to BibTex fields

- Work `place1` does not indicate the actual publication place (i.e, city, country). Instead, it indicates the venue. It represents both BibTex `journal` and BibTex `booktitle` attributes.

- However, `place1` is expected to be used only as a fallback for a lack of `place` field. The `place` field has the same semantics of `place1`, but it uses `Place` objects defined in `database/places.py`. Defining Place objects is harder than just adding Work with string venues.

Finally, it is hard to distinguish tool-attributes from bibtex-fields, when looking at the work. For instance:

- The user-defined `due` attribute that indicates why a tool is unrelated to the snowballing subject should not be exported to BibTex

- Similarly, the tool-defined `category` attribute that indicates the state of the Work in the snowballing should no be exported as well


While this profile has these drawbacks, it also has some positive aspects:

- The Place objects keep the database consistent and allow to group Work by venue

- This profiles has been heavily tested in actual literature reviews


### BibTex Profile

This profiles seeks to be more user-friendly by using BibTex fields as Work attributes and using `_` as a prefix to distinguish user-attributes from BibTex fields. Hence, in comparison to the `default` profile:

- `name` became `title`

- `pp` became `pages`

- `authors` became `author`

- `place1` and `place` were removed. This profile uses `journal` and `booktitle` as strings instead

- `due` became `_due`

- `category` became `_category`

- `link` became `_url`

In addition to these changes, we also removed the `display` and `may_be_related_to` attributes, but it is possible to add them back in the configuration.

With this profile, it is easier to work without breaking the database (as you don't need to specify existing Place objects), and it is easier to identify which attributes should be exported to BibTex when you use the search function. 


Supporting tools
------------------

This tool uses other tools that require external installations to assist in the literature review. You may or may not need them all. In this section, we present these tools and describe how to install them.

### John Snow Chrome Plugin

This plugin modifies the Google Scholar search page to include "BibTex", "Work", and "Add" buttons to assist in adding papers to the tool. It is specially helpful in the forward step of the snowballing, as it allows uses to configure a "citation_var", click on the "cited by" and add work with their citations.

To install it:
  - Use the following command to generate a folder with the Chrome plugin:
    - `$ snowballing plugin`
  - Activate the developer mode in Chrome and click in "Load unpacked" to load the plugin from the generated folder

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
- Validate.ipynb : Validate dabatase items by searching each item at Google Scholar and comparing their BibTex

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


### PDFReferencesExtractor

[PDFReferencesExtractor](https://github.com/helenocampos/PDFReferencesExtractor) is a helpful tool for extracting citations from PDFs to assist in backward snowballing. It is integrated into the Converter widget of the notebook Backward.ipynb.

To install it:
  - Clone the repository https://github.com/helenocampos/PDFReferencesExtractor
  - Install Java and Maven
  - Run `$ mvn install`
  - Configure the variable `config.PDF_EXTRACTOR` in your `database/__init__.py` to something link `"java -jar refExtractor.jar full {path}"`. Note that `java` must be in your path, and `refExtractor.jar` refer to the compiled PDFReferencesExtractor file that was generated into the `target` directory

To use it:
  - Run the Converter Widget in Backward.ipynb
  - Select the "PDF" mode
  - Write the PDF path (or drag a PDF file into the input textarea)
  - It will generate a BibTex in the output area
  - Change the mode to BibTex to generate a list of Info structures
  - Click on "Set article_list" to save the list into a variable
  - Run the remainder of the notebook to use it


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

