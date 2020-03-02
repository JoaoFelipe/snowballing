let citation_var = document.getElementById('citation-var');
let citation_file = document.getElementById('citation-file');
let backward = document.getElementById('backward');
let reload = document.getElementById('reload');
let errors = document.getElementById

chrome.storage.sync.get([
  'citation_var',
  'citation_file',
  'backward'
], function(data) {
  citation_var.value = data.citation_var;
  citation_file.value = data.citation_file;
  backward.checked = data.backward;
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

reload.addEventListener('click', (element) => {
  chrome.tabs.query({currentWindow: true, active: true}, function (tabs){
    var activeTab = tabs[0];
    chrome.tabs.sendMessage(activeTab.id, {"message": "reload"});
  });
});

