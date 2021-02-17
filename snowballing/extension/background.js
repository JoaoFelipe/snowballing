// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';
function setPageActionIcon(tab, color, text) {
  var canvas = document.createElement('canvas');
  var img = document.createElement('img');
  img.onload = function () {
    /* Draw the background image */
    var context = canvas.getContext('2d');
    context.drawImage(img, 0, 0);

    if (text) {
      
        /* Draw some text */
        context.fillStyle = "black";
        context.font = "9px Sans-Serif";
        context.textAlign = "center";
        context.fillText(text, 7.9, 11.5);
    }
    chrome.pageAction.setIcon({
        imageData: context.getImageData(0, 0, 16, 16),
        tabId:     tab.id
    });
  };
  img.src = `img/${color}16.png`;
}


chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  if (request.message == "count") {
      setPageActionIcon(sender.tab, request.color, request.text);
      let detail = {
        "tabId": sender.tab.id,
        "title": ("Snowballing" + request.tooltip)
      }
      chrome.pageAction.setTitle(detail, () => {});
      sendResponse(request.text)
  }
  if (request.message == "fetch") {
    fetch(request.input, request.init).then(function(response) {
      return response.text().then(function(text) {
        sendResponse([{
          body: text,
          status: response.status,
          statusText: response.statusText,
        }, null]);
      });
    }, function(error) {
      sendResponse([null, error]);
    });
  }
  return true;

});


chrome.runtime.onInstalled.addListener(function() {
  chrome.storage.sync.set({
    'citation_var': "",
    "citation_file": "",
    "backward": false,
    "url": 'http://localhost:5000',
    "show_snowballing": true,
    "show_search": false
  });
  chrome.declarativeContent.onPageChanged.removeRules(undefined, function() {
    chrome.declarativeContent.onPageChanged.addRules([{
      conditions: [
        new chrome.declarativeContent.PageStateMatcher({
          pageUrl: {hostEquals: 'scholar.google.com'},
        }),
        new chrome.declarativeContent.PageStateMatcher({
          pageUrl: {hostEquals: 'scholar.google.com.br'},
        }),
      ],
          actions: [new chrome.declarativeContent.ShowPageAction()]
    }]);
  });
});



/*
chrome.browserAction.onClicked.addListener(function(tab) { 
  chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    chrome.tabs.insertCSS(
      tabs[0].id, {file: 'style.css'},
      function() {
        chrome.tabs.executeScript(
          tabs[0].id, {file: 'jquery-3.4.1.min.js'},
          function() {
            chrome.tabs.executeScript(
              tabs[0].id, {file: 'content.js'}
            );
          }
        );
      }
    );
  });
});

*/