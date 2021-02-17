let snowballingbtn = document.getElementById('snowballingbtn');
let searchbtn = document.getElementById('searchbtn');
let snowballingdiv = document.getElementById('snowballing');
let searchdiv = document.getElementById('search');

let citation_var = document.getElementById('citation-var');
let citation_file = document.getElementById('citation-file');
let backward = document.getElementById('backward');
let reload = document.getElementById('reload');
let citedby = document.getElementById('citedby');

let scitation_var = document.getElementById('scitation-var');
let goto = document.getElementById('goto');
let bytitle = document.getElementById('bytitle');



let errors = document.getElementById

snowballingbtn.addEventListener('click', (element) => {
  if (snowballingdiv.style.display === "none") {
    snowballingdiv.style.display = "block";
    snowballingbtn.classList.add('down');
    chrome.storage.sync.set({
      'show_snowballing': true
    });
  } else {
    snowballingdiv.style.display = "none";
    snowballingbtn.classList.remove('down');
    chrome.storage.sync.set({
      'show_snowballing': false
    });
  }
});

searchbtn.addEventListener('click', (element) => {
  if (searchdiv.style.display === "none") {
    searchdiv.style.display = "block";
    searchbtn.classList.add('down');
    chrome.storage.sync.set({
      'show_search': true
    });
  } else {
    searchdiv.style.display = "none";
    searchbtn.classList.remove('down');
    chrome.storage.sync.set({
      'show_search': false
    });
  }
});

chrome.storage.sync.get([
  'citation_var',
  'citation_file',
  'backward',
  'show_snowballing',
  'show_search'
], function(data) {
  citation_var.value = data.citation_var;
  citation_file.value = data.citation_file;
  backward.checked = data.backward;
  if (data.show_search) {
    searchbtn.click();
  }
  if (data.show_snowballing) {
    snowballingbtn.click();
  }
});

citation_var.addEventListener('input', (element) => {
  chrome.storage.sync.set({
    'citation_var': citation_var.value
  });
});
citation_file.addEventListener('input', (element) => {
  chrome.storage.sync.set({
    'citation_file': citation_file.value
  });
});

backward.addEventListener('change', (element) => {
  chrome.storage.sync.set({
    'backward': backward.checked
  });
});



function checkCitationVar(citation_var, scholarfn) {
  citation_var.classList.remove("invalid");
  chrome.storage.sync.get([
    'url',
  ], function(data) {
    fetch(data.url + "/simplefind?pyref=" + citation_var.value, {method: 'GET', headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    }})
    .then(function(res) {
      return res.json();
    })
    .then(function(response) {
      if (response.found && response.scholar) {
        if (scholarfn !== undefined) scholarfn(data, response);
      } else if (response.found === null) {
        citation_var.classList.add("invalid");
      }
    })
    
  });
}

reload.addEventListener('click', (element) => {
  chrome.tabs.query({currentWindow: true, active: true}, function (tabs){
    checkCitationVar(citation_var);
    var activeTab = tabs[0];
    chrome.tabs.sendMessage(activeTab.id, {"message": "reload"});
  });
});

citedby.addEventListener('click', (element) => {
  chrome.tabs.query({currentWindow: true, active: true}, function (tabs){
    checkCitationVar(citation_var, function(data, response) {
      chrome.tabs.update({ url: response.scholar })
    });
  });
});



goto.addEventListener('click', (element) => {
  chrome.tabs.query({currentWindow: true, active: true}, function (tabs){
    checkCitationVar(scitation_var);
    chrome.storage.sync.get([
      'url',
    ], function(data) {
      fetch(data.url + "/simpleclick?pyref=" + scitation_var.value, {method: 'GET', headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      }})
      .then(function(res) {
        return res.json();
      })
    });
  });
});


bytitle.addEventListener('click', (element) => {
  chrome.tabs.query({currentWindow: true, active: true}, function (tabs){
    checkCitationVar(scitation_var, function(data, response) {
      chrome.tabs.update({ url: "https://scholar.google.com/scholar?hl=en&as_sdt=0%2C5&btnG=&q=" + response.title });
    });
  });
});
