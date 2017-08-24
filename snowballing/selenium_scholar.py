"""
This module provides classes for querying Google Scholar using selenium and
parsing returned results. It currently *only* processes the first results
page. It is not a recursive crawler.
"""

# Based on scholar.py 2.10
#
# Don't complain about missing docstrings: pylint: disable-msg=C0111
#
# Copyright 2010--2014 Christian Kreibich. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#    1. Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import sys
import time

from collections import deque
from random import uniform

from selenium import webdriver
from selenium.webdriver.remote.errorhandler import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from .scholar import quote, encode, unquote
from .scholar import Error, FormatError, QueryArgumentError, ScholarConf
from .scholar import ScholarUtils, ScholarArticle, ScholarArticleParser120726
from .scholar import ScholarQuery, BeautifulSoup
from .operations import work_by_varname

ScholarConf.VERSION = 's1.00'
ScholarConf.DELTA_TIME = 1.0
ScholarConf.DELTA_VARIATION = 0.5


def get_scholar_url(work):
    """ Gets scholar url from work """
    scholar_url = list(urlparse(work.scholar))
    scholar_url[0] = "http"
    scholar_url[1] = "scholar.google.com"
    scholar_url[4] = urlencode(
        {"cites": parse_qs(scholar_url[4])["cites"]},
        doseq=True
    )
    return urlunparse(scholar_url)


def click(parent, selector):
    """ Clicks on selector """
    element = parent.find_element_by_css_selector(selector)
    element.click()
    return element


class URLQuery(ScholarQuery):
    """ Represents a Google Scholar query using a generic query
    We use it to navigate on the citations """

    def __init__(self, url, start=None):
        ScholarQuery.__init__(self)
        self.start = start

        self.url = url


    def get_url(self):
        url = self.url
        if self.start is not None:
            url += "&" if "?" in url else "?"
            url += "start={}".format(self.start)
        return url


class Result(object):
    """ Represents a result with articles """

    def __init__(self, query, html):
        self.articles = []
        self.query = query
        self.html = html
        self.next_page = None
        self.prev_page = None

    def set_navigation(self, driver, name, text):
        try:
            link = driver.find_element_by_link_text(text)
            setattr(self, name, URLQuery(link.get_attribute("href")))
        except NoSuchElementException:
            pass


class AddArticleTask(object):
    """ Task that adds an article to the result """

    def __init__(self, result, article):
        self.article = article
        self.result = result

    def get_citation_data(self, querier):
        """
        Given an article, retrieves citation link. Note, this requires that
        you adjusted the settings to tell Google Scholar to actually
        provide this information, *prior* to retrieving the article.
        """
        if self.article['url_citation'] is None:
            return False
        if self.article.citation_data is not None:
            return True

        ScholarUtils.log('info', 'retrieving citation export data: {}'.format(
            self.article["url_citation"]
        ))
        data = querier.get_response(url=self.article['url_citation'],
                                    log_msg='citation data response',
                                    err_msg='requesting citation data failed',
                                    condition=(By.TAG_NAME, 'pre'))
        soup = BeautifulSoup(data, "html.parser")
        data = soup.text
        if data is None:
            querier.tasks.appendleft(self)
            raise Error("Connection error")

        self.article.set_citation_data(data)
        return True

    def apply(self, querier):
        if len(self.result.articles) < getattr(self.result.query, 'num_results', 10000):
            self.get_citation_data(querier)
            self.result.articles.append(self.article)


class ParseTask(ScholarArticleParser120726):
    """ Task that parsers articles """

    def __init__(self, result):
        ScholarArticleParser120726.__init__(self)
        self.result = result
        self.querier = None
        self.articles = []

    def handle_num_results(self, num_results):
        if self.result is not None and self.result.query is not None:
            self.result.query['num_results'] = num_results

    def handle_article(self, art):
        self.articles.append(art)

    def apply(self, querier):
        self.querier = querier
        self.parse(self.result.html)
        for art in reversed(self.articles):
            self.querier.tasks.appendleft(AddArticleTask(self.result, art))



class QueryTask(object):
    """ Task that queries the scholar """

    def __init__(self, query):
        self.query = query

    def apply(self, querier):
        html = querier.get_response(url=self.query.get_url(),
                                    log_msg='dump of query response HTML',
                                    err_msg='results retrieval failed',
                                    condition=(By.ID, "gs_ab"))

        if html is None:
            querier.tasks.appendleft(self)
            raise Error("Connection error")

        querier.result = Result(self.query, html)
        querier.result.set_navigation(querier.driver, "next_page", "Next")
        querier.result.set_navigation(querier.driver, "prev_page", "Previous")

        querier.tasks.appendleft(ParseTask(querier.result))


class SearchScholarQuery(ScholarQuery):
    """
    This version represents the search query parameters the user can
    configure on the Scholar website, in the advanced search options.
    """

    SCHOLAR_QUERY_URL = ScholarConf.SCHOLAR_SITE + '/scholar?'

    def __init__(self):
        ScholarQuery.__init__(self)
        self._add_attribute_type('num_results', 'Results', 0)
        self.words = None # The default search behavior
        self.words_some = None # At least one of those words
        self.words_none = None # None of these words
        self.phrase = None
        self.scope_title = False # If True, search in title only
        self.author = None
        self.pub = None
        self.timeframe = [None, None]
        self.include_patents = True
        self.include_citations = True

    def set_words(self, words):
        """Sets words that *all* must be found in the result."""
        self.words = words

    def set_words_some(self, words):
        """Sets words of which *at least one* must be found in result."""
        self.words_some = words

    def set_words_none(self, words):
        """Sets words of which *none* must be found in the result."""
        self.words_none = words

    def set_phrase(self, phrase):
        """Sets phrase that must be found in the result exactly."""
        self.phrase = phrase

    def set_scope(self, title_only):
        """
        Sets Boolean indicating whether to search entire article or title
        only.
        """
        self.scope_title = title_only

    def set_author(self, author):
        """Sets names that must be on the result's author list."""
        self.author = author

    def set_pub(self, pub):
        """Sets the publication in which the result must be found."""
        self.pub = pub

    def set_timeframe(self, start=None, end=None):
        """
        Sets timeframe (in years as integer) in which result must have
        appeared. It's fine to specify just start or end, or both.
        """
        if start:
            start = ScholarUtils.ensure_int(start)
        if end:
            end = ScholarUtils.ensure_int(end)
        self.timeframe = [start, end]

    def set_include_citations(self, yesorno):
        self.include_citations = yesorno

    def set_include_patents(self, yesorno):
        self.include_patents = yesorno

    def get_url(self):
        if self.words is None and self.words_some is None \
           and self.words_none is None and self.phrase is None \
           and self.author is None and self.pub is None \
           and self.timeframe[0] is None and self.timeframe[1] is None:
            raise QueryArgumentError('search query needs more parameters')

        # If we have some-words or none-words lists, we need to
        # process them so GS understands them. For simple
        # space-separeted word lists, there's nothing to do. For lists
        # of phrases we have to ensure quotations around the phrases,
        # separating them by whitespace.
        words_some = None
        words_none = None

        if self.words_some:
            words_some = self._parenthesize_phrases(self.words_some)
        if self.words_none:
            words_none = self._parenthesize_phrases(self.words_none)

        urlargs = [
            ("as_q", self.words or ''),
            ("as_epq", self.phrase or ''),
            ("as_oq", words_some or ''),
            ("as_eq", words_none or ''),
            ("as_occt", 'title' if self.scope_title else 'any'),
            ("as_sauthors", self.author or ''),
            ("as_publication", self.pub or ''),
            ("as_ylo", self.timeframe[0] or ''),
            ("as_yhi", self.timeframe[1] or ''),
            ("as_sdt", ('0' if self.include_patents else '1') + "%2C5"),
            ("as_vis", '0' if self.include_citations else '1'),
        ]

        args = "&".join(
            "{}={}".format(key, quote(encode(value))) for key, value in urlargs
         #   if value
        )
        return self.SCHOLAR_QUERY_URL + args + "&btnG=&hl=en"


def wait_for(driver, condition, delay=5):
    """ Wait for an element appear during :delay seconds """
    WebDriverWait(driver, delay).until(EC.visibility_of_element_located(condition))


def check_captcha(driver, condition):
    """ Check if it expects a captcha """
    captcha = driver.find_elements_by_css_selector("#captcha")
    captcha += driver.find_elements_by_css_selector("#gs_captcha_f")
    captcha += driver.find_elements_by_css_selector("#g-recaptcha")
    captcha += driver.find_elements_by_css_selector("#recaptcha")
    while captcha:
        print("Ops. It requires a captcha!")
        print("If you filled in the browser, type '<ok>' here.")
        inp = input("Captcha: ")
        if inp == "<ok>":
            break
        captcha[0].send_keys(inp)
        captcha[0].send_keys(Keys.RETURN)
        try:
            if condition:
                wait_for(driver, condition)
            break
        except TimeoutException:
            captcha = driver.find_elements_by_css_selector("#captcha")


class ScholarSettingsTask(object):
    """
    This class lets you adjust the Scholar settings for your
    session.
    """
    CITFORM_NONE = 0
    CITFORM_REFWORKS = 1
    CITFORM_REFMAN = 2
    CITFORM_ENDNOTE = 3
    CITFORM_BIBTEX = 4

    COLLECTIONS_ARTICLES_ONLY = 0
    COLLECTIONS_ARTICLES_AND_PATENTS = 1
    COLLECTIONS_CASE_LAW = 2

    SETTINGS_URL = (
    	ScholarConf.SCHOLAR_SITE +
    	'/scholar_settings?hl=en&as_sdt=0,5&sciodt=0,5'
    )

    def __init__(self, pages=10, citform=0, new_window=False, collections=1):
        self.is_configured = False
        self.citform = citform
        self.per_page_results = pages
        self.new_window = new_window
        self.collections = 1

    @property
    def citform(self):
        return self._citform

    @citform.setter
    def citform(self, value):
        value = ScholarUtils.ensure_int(value)
        if not 0 <= value <= 4:
            raise FormatError("Error: 'citform' must be between 0 and 4")
        if value != 0:
            self.is_configured = True
        self._citform = value

    @property
    def per_page_results(self):
        return self._per_page_results

    @per_page_results.setter
    def per_page_results(self, value):
        value = ScholarUtils.ensure_int(value, 'page results must be integer')
        if value not in {10, 20}:
            raise FormatError("Error: 'pages' must be either 10 or 20")
        if value != 10:
            self.is_configured = True
        self._per_page_results = value

    @property
    def new_window(self):
        return self._new_window

    @new_window.setter
    def new_window(self, value):
        if value:
            self._is_configured = True
        self._new_window = value

    @property
    def collections(self):
        return self._collections

    @collections.setter
    def collections(self, value):
        value = ScholarUtils.ensure_int(value)
        if not 0 <= value <= 2:
            raise FormatError("Error: 'collections' must be between 0 and 2")
        if value != 1:
            self._is_configured = True
        self._collections = value

    def apply(self, querier):
        driver = querier.driver
        if not self.is_configured:
            return
        driver.get(ScholarSettingsTask.SETTINGS_URL)
        check_captcha(driver, (By.ID, "gs_num-bd"))


        results_per_page = click(driver, "#gs_num-bd")
        twenty_results = click(
        	results_per_page.parent,
        	'li[data-v="{}"]'.format(self.per_page_results)
        )
        if self.citform != 0:
            cittype = click(driver, "#gs_scisf-bd")
            bibtex = click(
            	cittype.parent, 'li[data-v="{}"]'.format(self.citform)
            )
        else:
            dont_show = click(driver, "#scis0")

        if self.new_window:
            new_window = click(driver, "#gs_nw")

        case_laws = click(driver, "#as_sdt2")
        if self.collections < 3:
            articles = click(driver, "#as_sdt1")
        if self.collections == 1:
            patents = click(driver, "#as_sdtp")

        save_button = click(driver, '.gs_btn_act[name="save"]')
        ScholarUtils.log('info', 'settings applied')


class SeleniumScholarQuerier(object):
    """
    ScholarQuerier instances can conduct a search on Google Scholar
    with subsequent parsing of the resulting HTML content.  The
    articles found are collected in the articles member, a list of
    ScholarArticle instances.
    """

    def __init__(self, driver=None):
        self.result = None
        self.articles = []
        self.driver = driver or webdriver.Firefox()
        self.tasks = deque()
        self.last_request = time.time() - ScholarConf.DELTA_TIME - 1

    def continue_tasks(self):
        while self.tasks:
            task = self.tasks.popleft()
            task.apply(self)
        if self.result:
            self.articles = self.result.articles

    def apply_settings(self, *args, **kwargs):
        """Applies settings"""
        settings = ScholarSettingsTask(*args, **kwargs)
        self.tasks.append(settings)
        self.continue_tasks()
        return self

    def send_query(self, query):
        """Initiates a search query (a ScholarQuery instance)"""
        self.tasks.append(QueryTask(query))
        self.continue_tasks()
        return self

    def get_response(self, url, log_msg=None, err_msg=None, condition=None):
        """
        Helper method, sends HTTP request and returns response payload.
        """
        if log_msg is None:
            log_msg = 'HTTP response data follow'
        if err_msg is None:
            err_msg = 'request failed'
        try:
            ScholarUtils.log('info', 'requesting %s' % unquote(url))

            current = time.time()
            while current - ScholarConf.DELTA_TIME < self.last_request:
                time.sleep(self.last_request - current + ScholarConf.DELTA_TIME)
                current = time.time()

            self.driver.get(url)
            self.last_request = time.time() + uniform(
                -ScholarConf.DELTA_VARIATION, ScholarConf.DELTA_VARIATION
            )
            check_captcha(self.driver, condition)

            html = self.driver.page_source

            ScholarUtils.log('debug', log_msg)
            ScholarUtils.log('debug', '>>>>' + '-'*68)
            ScholarUtils.log('debug', 'url: %s' % self.driver.current_url)
            ScholarUtils.log('debug', 'data:\n' + html) # For Python 3
            ScholarUtils.log('debug', '<<<<' + '-'*68)

            return html
        except Exception as err:
            ScholarUtils.log('error', err_msg + ': %s' % err)
            return None
