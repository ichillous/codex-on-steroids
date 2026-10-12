/* Blueprint runtime: makes plain HTML pages behave like the real thing, with no build step.
   Load it at the end of <body>:  <script src="blueprint.js"></script>

   State is a flat map of short strings, for example { step: "form", viewer: "visitor" }.
   It starts from <body data-state="step=form; viewer=visitor"> and from the page address
   (page.html?viewer=member), and changes when someone presses a control.

   On any element:
     data-when="step=sent"        show only while the condition holds
                                  (forms: key  !key  key=a  key!=a  key=a|b  joined with " & ")
     data-set="step=sent"         pressing it sets state (several pairs: "step=sent; saved=on")
     data-toggle="saved"          pressing it switches a key between "on" and ""
     data-flash="Link copied."    pressing it shows a short status message
     data-off-when="!email"       looks and acts unavailable while the condition holds
     data-bind="email"            a field whose value is kept in state
     data-text="email"            its text follows a state value
     aria-pressed="false"         on a data-set control: kept true while its state is the current one
   On <form>:  data-set="step=sent"   applied on submit, after the browser's own required-field checks
   On <body>:  data-keep="viewer"     carry these keys to the next page when a link is followed
               data-variants="viewer=visitor|member"   states a reviewer can switch between
*/
(function () {
  'use strict';
  var body = document.body;
  var state = {};
  var toastTimer = null;

  function pairs(text) {
    return String(text || '').split(';').map(function (p) { return p.trim(); }).filter(Boolean).map(function (p) {
      var i = p.indexOf('=');
      return i < 0 ? [p, 'on'] : [p.slice(0, i).trim(), p.slice(i + 1).trim()];
    });
  }
  function holds(cond) {
    return String(cond || '').split('&').every(function (term) {
      term = term.trim();
      if (!term) return true;
      var m = term.match(/^([\w-]+)\s*(!=|=)\s*(.*)$/);
      if (m) {
        var hit = m[3].split('|').map(function (v) { return v.trim(); }).indexOf(state[m[1]] || '') >= 0;
        return m[2] === '=' ? hit : !hit;
      }
      return term.charAt(0) === '!' ? !state[term.slice(1).trim()] : !!state[term];
    });
  }
  function each(selector, fn) { Array.prototype.forEach.call(document.querySelectorAll(selector), fn); }

  function render() {
    each('[data-when]', function (el) { el.hidden = !holds(el.getAttribute('data-when')); });
    each('[data-off-when]', function (el) {
      var off = holds(el.getAttribute('data-off-when'));
      el.classList.toggle('off', off);
      if (off) el.setAttribute('aria-disabled', 'true'); else el.removeAttribute('aria-disabled');
    });
    each('[data-set][aria-pressed]', function (el) {
      var on = pairs(el.getAttribute('data-set')).every(function (p) { return (state[p[0]] || '') === p[1]; });
      el.setAttribute('aria-pressed', on ? 'true' : 'false');
      el.classList.toggle('on', on);
    });
    each('[data-toggle]', function (el) {
      var on = !!state[el.getAttribute('data-toggle')];
      el.setAttribute('aria-pressed', on ? 'true' : 'false');
      el.classList.toggle('on', on);
    });
    each('[data-text]', function (el) {
      var v = state[el.getAttribute('data-text')];
      if (v !== undefined && v !== '') el.textContent = v;
    });
    each('[data-bind]', function (el) {
      var v = state[el.getAttribute('data-bind')] || '';
      if (el.type === 'checkbox') el.checked = !!v;
      else if (el.type === 'radio') el.checked = el.value === v;
      else if (el.value !== v && document.activeElement !== el) el.value = v;
    });
    var keep = (body.getAttribute('data-keep') || '').split(/[\s,;]+/).filter(Boolean);
    if (keep.length) each('a[href]', function (a) {
      if (a.hasAttribute('data-blueprint-ui')) return;
      var href = a.getAttribute('data-href0') || a.getAttribute('href');
      if (!href || /^(#|[a-z][a-z0-9+.-]*:)/i.test(href)) return;
      a.setAttribute('data-href0', href);
      var hash = '', i = href.indexOf('#');
      if (i >= 0) { hash = href.slice(i); href = href.slice(0, i); }
      var q = keep.filter(function (k) { return state[k] && !new RegExp('[?&]' + k + '=').test(href); })
        .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(state[k]); }).join('&');
      a.setAttribute('href', href + (q ? (href.indexOf('?') >= 0 ? '&' : '?') + q : '') + hash);
    });
  }
  function set(text) { pairs(text).forEach(function (p) { state[p[0]] = p[1]; }); render(); }

  function flash(text) {
    var t = document.querySelector('.toast');
    if (!t) { t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); body.appendChild(t); }
    t.textContent = text; t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 2600);
  }

  /* Open decisions are written in [CAPITALS IN BRACKETS]; make them impossible to miss. */
  function markOpen() {
    var re = /\[[A-Z][A-Z0-9 %\/&'’.,:+-]{2,}\]/g, nodes = [];
    var walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, null);
    while (walker.nextNode()) {
      var n = walker.currentNode, p = n.parentNode;
      if (!p || /^(SCRIPT|STYLE|TEXTAREA|OPTION|MARK|TITLE)$/.test(p.nodeName)) continue;
      re.lastIndex = 0;
      if (re.test(n.nodeValue)) nodes.push(n);
    }
    nodes.forEach(function (n) {
      var frag = document.createDocumentFragment(), text = n.nodeValue, last = 0, m;
      re.lastIndex = 0;
      while ((m = re.exec(text))) {
        if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
        var mark = document.createElement('mark');
        mark.className = 'open'; mark.title = 'Open decision'; mark.textContent = m[0];
        frag.appendChild(mark); last = m.index + m[0].length;
      }
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      n.parentNode.replaceChild(frag, n);
    });
  }

  /* A small bar for the person reviewing: back to the map, and a switch for each declared variant. */
  function reviewBar() {
    if (document.querySelector('.bp-bar')) return;
    var bar = document.createElement('nav');
    bar.className = 'bp-bar'; bar.setAttribute('data-blueprint-ui', ''); bar.setAttribute('aria-label', 'Blueprint review');
    function link(label, href, on) {
      var a = document.createElement('a');
      a.textContent = label; a.href = href; a.setAttribute('data-blueprint-ui', '');
      if (on) a.setAttribute('aria-current', 'true');
      bar.appendChild(a);
    }
    link('Map', 'map.html', false);
    pairs(body.getAttribute('data-variants')).forEach(function (v) {
      var label = document.createElement('span'); label.textContent = v[0]; bar.appendChild(label);
      v[1].split('|').forEach(function (opt) {
        opt = opt.trim();
        var q = new URLSearchParams(location.search); q.set(v[0], opt);
        link(opt, location.pathname.split('/').pop() + '?' + q.toString(), (state[v[0]] || '') === opt);
      });
    });
    body.appendChild(bar);
  }

  function control(el) {
    while (el && el !== body) {
      if (el.hasAttribute && (el.hasAttribute('data-set') || el.hasAttribute('data-toggle') || el.hasAttribute('data-flash'))) return el;
      el = el.parentNode;
    }
    return null;
  }

  document.addEventListener('click', function (ev) {
    var el = control(ev.target);
    if (!el || el.nodeName === 'FORM') return;
    if (el.getAttribute('aria-disabled') === 'true' || el.disabled) { ev.preventDefault(); return; }
    if (el.nodeName === 'A' && !el.getAttribute('href')) ev.preventDefault();
    if (el.hasAttribute('data-toggle')) { var k = el.getAttribute('data-toggle'); state[k] = state[k] ? '' : 'on'; }
    if (el.hasAttribute('data-set')) pairs(el.getAttribute('data-set')).forEach(function (p) { state[p[0]] = p[1]; });
    render();
    if (el.hasAttribute('data-flash')) flash(el.getAttribute('data-flash'));
  });
  document.addEventListener('submit', function (ev) {
    var f = ev.target;
    if (!f.hasAttribute || !f.hasAttribute('data-set')) return;
    ev.preventDefault();
    set(f.getAttribute('data-set'));
    if (f.hasAttribute('data-flash')) flash(f.getAttribute('data-flash'));
  });
  function bound(ev) {
    var el = ev.target;
    if (!el.hasAttribute || !el.hasAttribute('data-bind')) return;
    state[el.getAttribute('data-bind')] = el.type === 'checkbox' ? (el.checked ? 'on' : '') : el.value;
    render();
  }
  document.addEventListener('input', bound);
  document.addEventListener('change', bound);

  each('[data-bind]', function (el) {            // fields start the state they are bound to
    var k = el.getAttribute('data-bind');
    if (el.type === 'checkbox') { if (el.checked) state[k] = 'on'; }
    else if (el.type === 'radio') { if (el.checked) state[k] = el.value; }
    else if (el.value) state[k] = el.value;
  });
  pairs(body.getAttribute('data-state')).forEach(function (p) { state[p[0]] = p[1]; });
  pairs(body.getAttribute('data-variants')).forEach(function (v) {   // first option is the default
    if (state[v[0]] === undefined) state[v[0]] = v[1].split('|')[0].trim();
  });
  new URLSearchParams(location.search).forEach(function (v, k) { state[k] = v; });

  markOpen();
  render();
  reviewBar();
  window.blueprint = { state: state, set: set, flash: flash, holds: holds };
})();
