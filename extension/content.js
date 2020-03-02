function fetchResource(input, init) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({message:"fetch", input:input, init:init}, messageResponse => {
      const [response, error] = messageResponse;
      if (response === null) {
        reject(error);
      } else {
        // Use undefined on a 204 - No Content
        const body = response.body ? new Blob([response.body]) : undefined;
        resolve(new Response(body, {
          status: response.status,
          statusText: response.statusText,
        }));
      }
    });
  });
}

function updateCount(color, text, tooltip){
    chrome.runtime.sendMessage({
        message:"count",
        color:color,
        text:text,
        tooltip: (tooltip? ": " + tooltip : "")
    });
}

function getConfig(func) {
    chrome.storage.sync.get([
        'citation_var',
        'citation_file',
        'backward',
        'url'
    ], function(data) {
        func(
            data.url,
            data.citation_var,
            data.citation_file,
            data.backward
        );
    });
}

function getRunning(success, error) {
    getConfig((url, citation_var, citation_file, backward) => {
        fetchResource(url + '/ping', {
            'method': 'post',
            'body': {},
            'headers': {
                'Content-type': 'application/json',
            }
        })
        .then((response) => response.json())
        .then((data) => {
            if (data.result == "ok") {
                success();
            } else {
                error();
                updateCount("red", "S", "Server offline");
            }
        })
        .catch((err) => {
            error();
            updateCount("red", "S", "Server offline");
        });
    })
    
}

function addError(item, msg, source) {
    let error = new Error;
    console.log(item);
    console.log(source);
    console.log(error);
    console.log(msg);
    let split = error.stack.split("\n")[1].split(':') 
    let line = split[split.length - 2];
    $(item).find('.snowballing .error-list').append(`
        <li>${line}:${source}: ${msg}</li>
    `);
    $(item).find('.snowballing .clear-list').show();
}

function unifiedParam(meta, citation_var, citation_file, backward, other) {
    let r1 = {
        'info': meta.info,
        'scholar_id': meta.scholar_id,
        'scholar': meta.scholar,
        'cluster_id': meta.cluster_id,
        'scholar_ok': meta.scholar_ok,
        'latex': meta.latex,
        'db_latex': meta.db_latex,
        'citation_var': citation_var,
        'citation_file': citation_file,
        'backward': backward,
    }
    if (!other) {
        return JSON.stringify(r1);
    }
    return JSON.stringify({...r1, ...other});
}

function fillStatus(data) {
    if (data.status && data.status.length > 0) {
        $('.snowballing-global .global-errors').html("");
        $('.snowballing-global .toggle-global').text(`${data.status.length} warning(s)`)
        $('.snowballing-global .toggle-global').show();
        for (let line of data.status) {
            $('.snowballing-global .global-errors').append(`
                <li>${line}</li>
            `);
        }
    } else {
        $('.snowballing-global .toggle-global').hide();
        $('.snowballing-global .inner-global').hide();
        $('.snowballing-global .clear').hide();
        
    }
}

function fillResult(meta, item, source, after, error) {
    return function(data) {
        fillStatus(data) 
        if (data.result == "ok") {
            meta.info = data.info;
            meta.latex = data.latex;
            meta.db_latex = data.db_latex;
            meta.citation = data.citation;
            meta.found = data.found;
            meta.add = data.add;
            if (after) {
                after(data);
            }
        } else {
            addError(item, data.msg, source);
            if (error) {
                error(data);
            }
        }
    }
}


class EventRunner {

    constructor(meta, item, baseDiv) {
        this.item = item;
        this.baseDiv = baseDiv;
        this.meta = meta;

        let self = this;

        this.operations = {
            "if": function(event) {
                let condition = self.execute(event[0]);
                if (condition) {
                    return self.execute(event[1]);
                } else {
                    return self.execute(event[2]);
                }
                
            },
            "and": function(event) {
                for (let op of event) {
                    if (!self.execute(op)) {
                        return false;
                    }
                }
                return true;
                
            },
            "or": function(event) {
                for (let op of event) {
                    if (self.execute(op)) {
                        return true;
                    }
                }
                return false;
            },
            "==": function(event) {
                return self.accessAttr(event[0]) == self.accessAttr(event[1])
            },
            "!=": function(event) {
                return self.accessAttr(event[0]) != self.accessAttr(event[1])
            },
            ">": function(event) {
                return self.accessAttr(event[0]) > self.accessAttr(event[1])
            },
            ">=": function(event) {
                return self.accessAttr(event[0]) >= self.accessAttr(event[1])
            },
            "<": function(event) {
                return self.accessAttr(event[0]) < self.accessAttr(event[1])
            },
            "<=": function(event) {
                return self.accessAttr(event[0]) <= self.accessAttr(event[1])
            },
            "not": function(event) {
                return !self.accessAttr(event[0])
            },
            "+": function(event) {
                let result = self.accessAttr(event[0]);
                for (let element of event.slice(1)) {
                    result += self.accessAttr(element)
                } 
                return result;
            },
            "reload": function(event) {
                getConfig((url, citation_var, citation_file, backward) => {
                    let indexed = {};

                    $.map($(self.baseDiv).find("form").serializeArray(), function(n, i){
                        indexed[n['name']] = n['value'];
                    });
                    fetchResource(url + "/form/submit",  {
                        'method': 'post',
                        'body': unifiedParam(self.meta, citation_var, citation_file, backward, {
                            'values': indexed,
                            'citation_file': citation_file
                        }),
                        'headers': {
                            'Content-type': 'application/json',
                        }
                    })
                    .then((response) => response.json())
                    .then(fillResult(self.meta, self.item, "/form/submit", (data) => {
                        let code = data.resp.code;
                        if (code) {
                            $(self.baseDiv).find(".code").val(
                                data.resp.code
                            )
                            $(self.baseDiv).find(".code-area").show();
                            $(self.baseDiv).find("form").show();
                        } else {
                            $(self.baseDiv).find(".code-area").hide();
                            $(self.baseDiv).find("form").hide();
                        }
                        var notice = "";
                        for (let extra in data.resp.extra) {
                            let value = data.resp.extra[extra];
                            notice += `<div class="item">
                                <label> ${extra} </label>
                                <input value='${value}'></input>
                            </div>`;
                        }
                        for (let attr in data.resp.widgets_update) {
                            let value = data.resp.widgets_update[attr];
                            self.setAttr(attr, value);
                        }
                        $(self.baseDiv).find(".notice").html(notice);
                        resetWork(self.meta, self.item)

                    }))
                    .catch((error) => addError(self.item, error, "fetch reload"));
                });
            },
            "pyref": function(event) {
                console.log("pyref");
            },
            "update_info": function(event) {
                console.log("update_info");
            }
        }
            
    }

    accessAttr(attr) {
        let self = this;
        if (typeof attr == "string") { 
            if (attr.startsWith(":")) {
                return $(self.baseDiv).find(`[name="${attr.slice(1)}"]`).val()
            }
            if ((self.meta.info != undefined) && attr.startsWith(".")) {
                return self.meta.info[attr.slice(1)] || "";
            }
            attr = attr.replace("\\.", ".").replace("\\:", ":");
            return attr;
        } else {
            return self.execute(attr);
        }
    }

    setAttr(attr, value) {
        let self = this;
        let elem = $(self.baseDiv).find(`[name="${attr}"]`);
        if (elem.is(':checkbox')) {
            elem.attr("checked", true);
        } else {
            elem.val(value);
        }
        elem.trigger("input");
    }

    execute(event) {
        let self = this;
        if (Array.isArray(event)) {
            if (event.length > 0) {
                if (typeof event[0] == "string") {
                    if (!(event[0] in self.operations)) {
                        addError(self.item, `Event ${event[0]} not found`, 'EventRunner');
                    } else {
                        return self.operations[event[0]](event.slice(1));
                    }
                } else {
                    return event.map((inst) => self.execute(inst));
                }
            }
            
        } else if ((typeof event == "object") && (event != null)) {
            for (let key in event) {
                let value = event[key];
                self.setAttr(key, self.accessAttr(value));
            };
            return "=";
        } else {
            return event;
        }
    }
}

function getClusterId(item) {
    function getUrlParam(url, k) {
        if (url == undefined) {
            return undefined;
        }
        var p = {};
        url.replace(/[?&]+([^=&]+)=([^&]*)/gi, function (s, k, v) { p[k] = v })
        return k ? p[k] : p;
    }
    
    var clusterInfo = [
        ["a[href^='/scholar?cites=']", 'cites', ((elem) => elem.attr("href"))],
        ["a[href^='/scholar?cluster=']", 'cluster', ((elem) => elem.attr("href"))],
        [".gs_or_ggsm a[data-clk]", 'd', ((elem) => elem.data("clk"))],
        [".gs_rt a[data-clk]", 'd', ((elem) => elem.data("clk"))],
    ];

    for (let pattern of clusterInfo) {
        var elem = $(item).find(pattern[0]);
        var url = pattern[2](elem);
        var result = getUrlParam(url, pattern[1]);
        if (result){
            return result;
        }
    }
    return null;
}
function getClusterLink(item, cluster_id) {
    var elem = $(item).find("a[href^='/scholar?cites=']");
    var url = elem.attr("href");
    if (url) {
        return ["http://scholar.google.com/scholar" + url, true];
    } else if (cluster_id) {
        return [
            `http://scholar.google.com/scholar?cites=${cluster_id}&as_sdt=2005&sciodt=0,5&hl=en`,
            'generated'
        ]
    }
    return [null, false];
}

function inject() {
    $('body').prepend(`
        <div class="snowballing-global">
            <button class="toggle-global"> 0 errors </button>
            <button class="clear"> Clear </button> 
            <div class="inner-global">
                
                <ul class="global-errors">
                </ul>
            </div>
        </div>
    `)
    $('.snowballing-global .toggle-global').hide();
    $('.snowballing-global .inner-global').hide();
    $('.snowballing-global .clear').hide();
    
    $('.snowballing-global .toggle-global').bind("click", function() {
        $('.snowballing-global .inner-global').toggle();
        $('.snowballing-global .clear').toggle();
    })
    $('.snowballing-global .clear').bind("click", function() {
        getConfig((url, citation_var, citation_file, backward) => {
            fetchResource(url + '/clear', {
                'method': 'post',
                'body':  JSON.stringify({}),
                'headers': {
                    'Content-type': 'application/json',
                }
            })
            .then((response) => response.json())
            .then(fillStatus)
            .catch((error) => {
                console.log("Clear error: " + error);
            });
        })
    })
    

    $('.gs_r[data-cid]').each((key, item) => {
        let cluster_id = getClusterId(item);
        let link = getClusterLink(item, cluster_id);
        let cid = item.dataset.cid;
        let meta = {
            'scholar_id': cid,
            'cluster_id': cluster_id,
            'scholar': link[0],
            'scholar_ok': link[1],
            'latex': null,
            'db_latex': null,
            'info': null,
            'citation': false,
            'found': false,
            'add': false,
        }
        $(item).find(".snowballing").remove();
        $(item).append(`
            <div class="snowballing" id='snow-${cid}'>
                <div class="error">
                    <ul class="error-list">
                    </ul>    
                </div>
                
                <div class="work"></div>
                <div class="bibtex-type"></div>
                <textarea class="latex"></textarea>
                <div class="form"></form>
            </div>
        `);
    resetWork(meta, item);
    getRunning(
        () => {
                findWork(meta, item);
        },
        () => {}
    ) 
    });
}

function resetWork(meta, item) {
    $(item).find('.snowballing .work').html(`
        <button class="reload-db">Reload DB</button>
        <button class="get-latex">DB Bibtex</button>
        <button class="hide-latex">Hide Bibtex</button>
        <button class="scholar-latex">Scholar Bibtex</button>
        <button class="found"></button>
        <button class="add">Add</button>
        <button class="hide-add">Hide Add</button>
        <button class="clear-list">Clear Errors</button>
    `);

    if (!$(item).find('.snowballing .latex').val()) {
        $(item).find('.snowballing .scholar-latex').show();
        if (meta.db_latex != null) {
            $(item).find('.snowballing .get-latex').show();
        } else {
            $(item).find('.snowballing .get-latex').hide();
        }
        $(item).find('.snowballing .hide-latex').hide();
        $(item).find('.snowballing .latex').hide();
    } else {
        if ($(item).find('.snowballing .bibtex-type').text() == "DB Bibtex:") {
            $(item).find('.snowballing .get-latex').hide();
            $(item).find('.snowballing .scholar-latex').show();
        } else {
            $(item).find('.snowballing .scholar-latex').hide();
            if (meta.db_latex != null) {
                $(item).find('.snowballing .get-latex').show();
            } else {
                $(item).find('.snowballing .get-latex').hide();
            }
        }
        
        $(item).find('.snowballing .hide-latex').show();
        $(item).find('.snowballing .latex').show();
        $(item).find('.snowballing .latex').height(
            $(item).find('.snowballing .latex')[0].scrollHeight
        );
    }

    
    getRunning(
        () => {
            $(item).find('.snowballing .reload-db').show();
            if (meta.add) {
                // $(item).find('.snowballing .add').show();
                if ($(item).find('.snowballing .form').html().trim()) {
                    $(item).find('.snowballing .add').hide();
                    $(item).find('.snowballing .hide-add').show();
                } else {
                    $(item).find('.snowballing .add').show();
                    $(item).find('.snowballing .hide-add').hide();
                }
            } else {
                $(item).find('.snowballing .add').hide();
                $(item).find('.snowballing .hide-add').hide();
            }

            if (meta.found) {
                $(item).find('.snowballing .found').show();
                $(item).find('.snowballing .found').text(meta.info.pyref);
            } else {
                $(item).find('.snowballing .found').hide();
            }
        },
        () => {
            $(item).find('.snowballing .reload-db').hide();
            $(item).find('.snowballing .found').hide();
            $(item).find('.snowballing .add').hide();
            $(item).find('.snowballing .hide-add').hide();
        }
    ) 

    $(item).find('.snowballing .get-latex').bind('click', function() {
        $(item).find('.snowballing .latex').val(meta.db_latex);
        $(item).find('.snowballing .bibtex-type').text("DB Bibtex:");
        resetWork(meta, item);
    });
    $(item).find('.snowballing .scholar-latex').bind('click', function() {
        loadLatex(item,
            (latex) => {
                meta.latex = latex;
                $(item).find('.snowballing .bibtex-type').text("Scholar Bibtex:");
                $(item).find('.snowballing .latex').val(latex);
                getRunning(
                    () => {
                        findWork(meta, item);
                        resetWork(meta, item);
                    },
                    () => {
                        resetWork(meta, item);
                    }
                ) 
            },
            (type, error) => {
                addError(item, type + " " + error, "fetch loadLatex");
                $(item).find('.snowballing .latex').val("");
                $(item).find('.snowballing .bibtex-type').text("");
                resetWork(meta, item);
            }
        )
    });
    $(item).find('.snowballing .hide-latex').bind('click', function() {
        $(item).find('.snowballing .latex').val("");
        $(item).find('.snowballing .bibtex-type').text("");
        resetWork(meta, item);
    })

    $(item).find('.snowballing .reload-db').bind('click', function() {
        findWork(meta, item);
    })
    
    $(item).find('.snowballing .add').bind('click', function() {
        loadForm(meta, item);

    })

    $(item).find('.snowballing .hide-add').bind('click', function() {
        $(item).find('.snowballing .form').html("");
        resetWork(meta, item);
    })

    

    $(item).find('.snowballing .found').bind('click', function() {
        clickWork(meta, item);
    })

    if ($(item).find('.snowballing .error-list li').length) {
        $(item).find('.snowballing .clear-list').show();
    } else {
        $(item).find('.snowballing .clear-list').hide();
    }

    $(item).find('.snowballing .clear-list').bind('click', function() {
        $(item).find('.snowballing .error-list').html("");
        $(item).find('.snowballing .clear-list').hide();
    })

    }

    function findWork(meta, item, after) {
    getConfig((url, citation_var, citation_file, backward) => {
        fetchResource(url + '/find', {
            'method': 'post',
            'body': unifiedParam(meta, citation_var, citation_file, backward),
            'headers': {
                'Content-type': 'application/json',
            }
        })
        .then((response) => response.json())
        .then(fillResult(meta, item, "/find", (data) => {
            resetWork(meta, item);
            if (after) {
                after();
            }
        }))
        .catch((error) => {
            addError(item, error, "fetch findWork");
            resetWork(meta, item);
            if (after) {
                after();
            }
        });
    });

    setTimeout(() => {
        var total = $(".snowballing .add:visible").length + $(".snowballing .hide-add:visible").length;
        if (total) {
            updateCount("yellow", total, `${total} papers can be added`);
        } else {
            updateCount("green", total, `Great!`);

        }
    }, 1000);

}

function loadLatex(item, success, error) {
    // Based on Zotero: https://github.com/zotero/translators/blob/master/Google%20Scholar.js#L140
    var cid = item.dataset.cid;
    var citeUrl = 'https://scholar.google.com/scholar?q=info:' + cid + ':scholar.google.com/&output=cite&scirp=1';
    fetchResource(citeUrl, {}) 
    .then((response) => response.text())
    .then((citePage) => {
        var m = citePage.match(/href="((https?:\/\/[a-z\.]*)?\/scholar.bib\?[^"]+)/);
        if (!m) {
            //Saved lists and possibly other places have different formats for BibTeX URLs
            //Trying to catch them here (can't add test bc lists are tied to google accounts)
            m = citePage.match(/href="(.+?)">BibTeX<\/a>/);
        }
        if (!m) {
            var msg = "Could not find BibTeX URL";
            var title = citePage.match(/<title>(.*?)<\/title>/i);
            if (title) {
                if (title) msg += ' Got page with title "' + title[1] +'"';
            }
            error("Parsing", msg);
        }
        var temp = document.createElement("div");
        temp.innerHTML = m[1];
        var url = ("textContent" in temp ? temp.textContent : temp.innerText).replace(/ {2,}/g, " ");
        fetchResource(url, {})
        .then((response) => response.text())
        .then((latex) => success(latex))
        .catch((msg) => error("Second", msg));
    })
    .catch((msg) => error("First", msg));
}

function clickWork(meta, item) {
  getConfig((url, citation_var, citation_file, backward) => {
      fetchResource(url + '/click', {
          'method': 'post',
          'body': unifiedParam(meta, citation_var, citation_file, backward),
          'headers': {
              'Content-type': 'application/json',
          }
      })
      .then((response) => response.json())
      .then(fillResult(meta, item, "/click"))
      .catch((error) => {
          addError(item, error, 'fetch clickWork');
      });
  });
}

function processFormCreation(meta, item) {
  let baseDiv = $(item).find('.snowballing .form');
  return function(data){
      
      meta.info = data.info
      let form = data.form;
      let result = '';
      
      let widgets = {};
      let end = []
      let runner = new EventRunner(meta, item, baseDiv);

      if (!data.found) {
          $(form.widgets).each((i, widget) => {
              if (widget[0] == "text") {
                  let value = widget[3];
                  if (value == null){
                      value = "";
                  }
                  widgets[widget[2]] = `
                      <div class="widget-inline">
                          <label class="widget-label" title="${widget[1]}">${widget[1]}</label>
                          <input name="${widget[2]}" type="text" placeholder="" value="${value}">
                      </div>
                  `;
              } else if (widget[0] == "button") {
                  widgets[widget[2]] = `
                      <button class="widget-button" type="button" name="${widget[2]}">${widget[1]}</button>
                  `;
              } else if (widget[0] == "dropdown") {
                  widgets[widget[2]] = `
                      <div class="widget-inline">
                          <label class="widget-label" title="${widget[1]}">${widget[1]}</label>
                          <select name="${widget[2]}"> 
                  `
                  $(widget[4]).each((j, option) => {
                      widgets[widget[2]] += `<option value="${option}" ${(option == widget[3]? "selected" : "")}>${option}</option>`
                  })
                  widgets[widget[2]] += `
                          </select>
                      </div>
                  `
              } else if (widget[0] == "toggle") {
                  widgets[widget[2]] = `
                      <div class="widget-inline">
                          <label class="widget-label" title="${widget[1]}">
                          <input name="${widget[2]}" type="checkbox" placeholder="" ${(widget[3]? "checked": "")}>
                          ${widget[1]}
                          </label>
                          
                      </div>
                  `;
              } 
              
          })
          result += `<form>`;
          $(form.order).each((i, tup) => {
              result += `<div class="widget-box">`;
              $(tup).each((j, wid) => {
                  result += widgets[wid];
              });
              result += `</div>`;
          })

          result += `</form>`
          
          
          end.push(function() {
              $(form.events).each((i, event) => {
                  let jsevent = event[1];
                  if (jsevent == "observe") {
                      jsevent = "input";
                  }
              
                  $(baseDiv).find(`[name="${event[0]}"]`).bind(jsevent, function() {
                      runner.execute(event[2]);
                  });
              
              });
              
          })
          
      } else {
          //result += `<div> Found ${data.info.pyref} </div>`;
      }
      result += `<div class="code-area">`
      result += `<div class="code-buttons">
          <button class="reload"> Reload </button>
          <button class="run"> Run </button>
      </div>`
      result += `<textarea class="code"/>`
      result += `</div>`
      result += `<div class='notice'></div>`
      result += `<div class='stdout'></div>`
      result += `<div class='stderr'></div>`

      $(baseDiv).html(result);
      for (let fn of end) {
          fn();
      }
      $(baseDiv).find(`.reload`).bind("click", function() {
          runner.execute(["reload"]);
      });
      $(baseDiv).find(`.run`).bind("click", function() {
          getConfig((url, citation_var, citation_file, backward) => {
              fetchResource(url + "/run",  {
                  'method': 'post',
                  'body': JSON.stringify({
                      'code': $(baseDiv).find('.code').val(),
                  }),
                  'headers': {
                      'Content-type': 'application/json',
                  }
              })
              .then((response) => response.json())
              .then((data) => {
                  fillStatus(data);
                  if (data["result"] == "ok") {
                      $(baseDiv).find(".stdout").text(data.stdout);
                      $(baseDiv).find(".stderr").text(data.stderr);
                  } else {
                      addError(item, data["msg"], "run error")
                  }
                  runner.execute(["reload"]);
              })
              .catch((error) => addError(item, error, "fetch run"));
              
          });
      });
      runner.execute(["reload"]);
  }
}


function loadForm(meta, item) {
  

  function main() {
      getConfig((url, citation_var, citation_file, backward) => {
          fetchResource(url + "/form",  {
              'method': 'post',
              'body': unifiedParam(meta, citation_var, citation_file, backward),
              'headers': {
                  'Content-type': 'application/json',
              }
          })
          .then((response) => response.json())
          .then(fillResult(meta, item, "/form", processFormCreation(meta, item)))
          .catch((error) => addError(item, error, 'fetch loadForm'));
      });
  }

  if (!meta.latex) {
      loadLatex(item,
          (latex) => {
              meta.latex = latex;
              findWork(meta, item, () => main());
          },
          (type, error) => {
              addError(item, type + " " + error, "fetch loadLatex");
          }
      )
  } else {
      main();
  }
  
}

function loadPage() {
    inject();

}

window.addEventListener("load", loadPage, false);

chrome.runtime.onMessage.addListener(
    function(request, sender, sendResponse) {
        if (request.message === "reload") {
            $('.gs_r[data-cid] .snowballing').remove();
            $('.snowballing-global').remove();
            inject();
        }
    }
);