/* SpecTracer docs site — theme toggle, copy buttons, mobile nav, scrollspy. */
(function () {
  'use strict';

  // ---- theme -------------------------------------------------------------
  // The initial value is set by an inline script in <head> to avoid a flash.
  var toggle = document.querySelector('.theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('st-theme', next); } catch (e) { /* private mode */ }
    });
  }

  // ---- mobile nav --------------------------------------------------------
  var navToggle = document.querySelector('.nav-toggle');
  var navLinks = document.querySelector('.nav-links');
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', function () {
      var open = navLinks.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', String(open));
    });
  }

  // ---- copy buttons ------------------------------------------------------
  // Each button copies the text of the element named by data-copy-target,
  // or the <pre> inside its own .code block.
  function textFor(btn) {
    var sel = btn.getAttribute('data-copy-target');
    if (sel) {
      var el = document.querySelector(sel);
      return el ? el.textContent : '';
    }
    var block = btn.closest('.code');
    var pre = block && block.querySelector('pre');
    return pre ? pre.textContent : '';
  }

  document.querySelectorAll('.copy-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var text = textFor(btn).replace(/\s+$/, '');
      if (!text) return;
      var done = function () {
        btn.classList.add('copied');
        btn.setAttribute('aria-label', 'Copied');
        setTimeout(function () {
          btn.classList.remove('copied');
          btn.setAttribute('aria-label', 'Copy to clipboard');
        }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {});
      } else {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); done(); } catch (e) { /* no-op */ }
        document.body.removeChild(ta);
      }
    });
  });

  // ---- sidebar scrollspy -------------------------------------------------
  var subLinks = Array.prototype.slice.call(document.querySelectorAll('.sidebar .sub a[href^="#"]'));
  if (subLinks.length && 'IntersectionObserver' in window) {
    var byId = {};
    var targets = [];
    subLinks.forEach(function (a) {
      var el = document.getElementById(a.getAttribute('href').slice(1));
      if (el) { byId[el.id] = a; targets.push(el); }
    });

    var visible = new Set();
    var mark = function () {
      // Highlight the topmost heading currently in view.
      var best = null;
      targets.forEach(function (t) {
        if (visible.has(t.id) && (best === null || t.offsetTop < best.offsetTop)) best = t;
      });
      subLinks.forEach(function (a) { a.classList.remove('active'); });
      if (best && byId[best.id]) byId[best.id].classList.add('active');
    };

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) visible.add(e.target.id); else visible.delete(e.target.id);
      });
      mark();
    }, { rootMargin: '-80px 0px -70% 0px' });

    targets.forEach(function (t) { io.observe(t); });
  }
})();
