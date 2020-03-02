let url = document.getElementById('url');

chrome.storage.sync.get([
  'url',
], function(data) {
  url.value = data.url;
});

url.addEventListener('input', (element) => {
  chrome.storage.sync.set({
    'url': url.value
  });
});
