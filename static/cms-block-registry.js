/**
 * CMS block model: { id, type, props, style, children[], hidden?, locked? }
 * Shared by builder canvas and public site renderer.
 */
(function () {
  const uid = () =>
    "b_" + Math.random().toString(36).slice(2, 11) + Date.now().toString(36);

  const esc = (s) => {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  };

  /** Starter HTML for “About” style pages (editable in builder). */
  const ABOUT_PAGE_HTML =
    "<h1>About us</h1>" +
    "<p>We help you <strong>download and save</strong> public videos quickly. Paste a link, pick quality, and save to your device — no account required.</p>" +
    "<h2>How it works</h2>" +
    "<p>Copy the post URL, paste it on the home page, then download the file you need.</p>" +
    "<h2>What we support</h2>" +
    "<ul>" +
    "<li>Public video posts</li>" +
    "<li>Multiple qualities when available</li>" +
    "<li>Fast, simple workflow</li>" +
    "</ul>" +
    "<h2>Where you can use it</h2>" +
    "<p>Works in modern browsers on desktop and mobile. Questions? <a href=\"mailto:support@example.com\">Email us</a>.</p>";

  const BLOG_ARTICLE_HTML =
    "<h1>Your article title</h1>" +
    "<p class=\"cms-article-meta\">By Author · " +
    new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" }) +
    "</p>" +
    "<p>Start your story here. Use headings, lists, and links for readability.</p>" +
    "<h2>Section heading</h2>" +
    "<ul><li>First point</li><li>Second point</li></ul>" +
    "<p><a href=\"#\">Learn more</a></p>";

  const styleStr = (st) => {
    if (!st || typeof st !== "object") return "";
    return Object.entries(st)
      .filter(([, v]) => v != null && v !== "")
      .map(([k, v]) => {
        const css = k.replace(/([A-Z])/g, "-$1").toLowerCase();
        return css + ":" + v;
      })
      .join(";");
  };

  const defaults = {
    section: () => ({
      padding: "48px 24px",
      background: "linear-gradient(180deg, rgba(15,23,42,0.9), rgba(15,23,42,0.98))",
      borderRadius: "0",
    }),
    container: () => ({
      maxWidth: "1100px",
      margin: "0 auto",
      padding: "0 16px",
    }),
    grid: () => ({
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
      gap: "24px",
    }),
    column: () => ({ padding: "12px" }),
    heading: () => ({
      text: "Heading",
      level: 2,
      fontSize: "32px",
      fontWeight: "700",
      color: "#f8fafc",
      textAlign: "left",
    }),
    paragraph: () => ({
      text: "Paragraph text. Click to edit in the properties panel.",
      fontSize: "16px",
      color: "#94a3b8",
      textAlign: "left",
      lineHeight: "1.6",
    }),
    richtext: () => ({
      html: "<p>Rich text — select this block and use the <strong>editor</strong> in the properties panel.</p>",
    }),
    button: () => ({
      label: "Button",
      href: "#",
      variant: "primary",
    }),
    image: () => ({
      src: "https://images.unsplash.com/photo-1557683316-973673baf926?w=800&q=80",
      alt: "",
      width: "100%",
      borderRadius: "12px",
    }),
    video: () => ({
      src: "https://www.w3schools.com/html/mov_bbb.mp4",
      poster: "",
    }),
    hero: () => ({
      title: "Build faster",
      subtitle: "Ship landing pages without code.",
      padding: "80px 24px",
      background: "radial-gradient(ellipse at top, rgba(99,102,241,0.25), transparent 50%), #0f172a",
    }),
    navbar: () => ({
      brand: "Brand",
      links: "Home, Pricing, Blog, Contact",
    }),
    footer: () => ({
      text: "© " + new Date().getFullYear() + " Your company. All rights reserved.",
      links: "Privacy, Terms, Contact",
    }),
    testimonials: () => ({ quote: "This product changed our workflow.", author: "Alex M., CTO" }),
    pricing: () => ({
      plan: "Pro",
      price: "$29",
      period: "/mo",
      features: "Unlimited projects, Priority support, Analytics",
      cta: "Get started",
    }),
    faq: () => ({
      items:
        "What is this?|A page builder.; Is it free?|Start free anytime.; How to publish?|Click Publish.",
    }),
    blogCards: () => ({ title: "From the blog", subtitle: "Latest updates" }),
    features: () => ({
      items: "Fast|Lightning performance; Secure|Enterprise-grade; Flexible|Drag and drop",
    }),
    input: () => ({ placeholder: "Email", name: "email", inputType: "text" }),
    textarea: () => ({ placeholder: "Message", name: "message", rows: 4 }),
    submit: () => ({ label: "Submit" }),
  };

  function createBlock(type) {
    const d = defaults[type] ? defaults[type]() : {};
    const block = { id: uid(), type, props: d, style: {}, children: undefined };
    if (
      ["section", "container", "grid", "column", "hero", "navbar", "footer"].includes(type)
    ) {
      block.children = [];
    }
    return block;
  }

  function ensureChildren(block) {
    if (
      ["section", "container", "grid", "column", "hero", "navbar", "footer"].includes(block.type)
    ) {
      if (!Array.isArray(block.children)) block.children = [];
    }
  }

  function renderBlock(block, options) {
    const { editMode, selectedId, onSelect } = options || {};
    ensureChildren(block);
    const wrap = document.createElement("div");
    wrap.className = "cms-node";
    wrap.dataset.blockId = block.id;
    if (block.hidden) wrap.classList.add("cms-node--hidden");
    if (block.locked) wrap.classList.add("cms-node--locked");
    if (editMode) {
      wrap.classList.add("cms-node--edit");
      if (selectedId === block.id) wrap.classList.add("cms-node--selected");
      wrap.addEventListener("click", (e) => {
        e.stopPropagation();
        if (!block.locked && onSelect) onSelect(block.id);
      });
    }

    const innerStyle = { ...(block.props || {}), ...(block.style || {}) };
    const p = block.props || {};

    switch (block.type) {
      case "section":
      case "container":
      case "grid":
      case "column": {
        const el = document.createElement("div");
        el.setAttribute("style", styleStr(innerStyle));
        (block.children || []).forEach((ch) => el.appendChild(renderBlock(ch, options)));
        wrap.appendChild(el);
        break;
      }
      case "heading": {
        const h = document.createElement("h" + Math.min(6, Math.max(1, p.level || 2)));
        h.innerHTML = esc(p.text);
        h.setAttribute(
          "style",
          styleStr({
            fontSize: p.fontSize,
            fontWeight: p.fontWeight,
            color: p.color,
            textAlign: p.textAlign,
            margin: "0",
          }),
        );
        wrap.appendChild(h);
        break;
      }
      case "paragraph": {
        const el = document.createElement("p");
        el.innerHTML = esc(p.text).replace(/\n/g, "<br>");
        el.setAttribute(
          "style",
          styleStr({
            fontSize: p.fontSize,
            color: p.color,
            textAlign: p.textAlign,
            lineHeight: p.lineHeight,
            margin: "0",
          }),
        );
        wrap.appendChild(el);
        break;
      }
      case "richtext": {
        const div = document.createElement("div");
        div.className = "cms-richtext";
        div.innerHTML = p.html || "";
        wrap.appendChild(div);
        break;
      }
      case "button": {
        const a = document.createElement("a");
        a.href = esc(p.href || "#");
        a.textContent = p.label || "Button";
        const v = p.variant || "primary";
        const base =
          "display:inline-block;padding:12px 24px;border-radius:10px;font-weight:600;text-decoration:none;cursor:pointer;";
        const styles =
          v === "outline"
            ? base +
              "border:2px solid #6366f1;color:#a5b4fc;background:transparent;"
            : v === "ghost"
              ? base + "color:#94a3b8;background:transparent;"
              : base + "background:linear-gradient(135deg,#6366f1,#4f46e5);color:#fff;";
        a.setAttribute("style", styles);
        wrap.appendChild(a);
        break;
      }
      case "image": {
        const img = document.createElement("img");
        img.src = p.src || "";
        img.alt = p.alt || "";
        img.setAttribute(
          "style",
          styleStr({ width: p.width, borderRadius: p.borderRadius, maxWidth: "100%", display: "block" }),
        );
        wrap.appendChild(img);
        break;
      }
      case "video": {
        const v = document.createElement("video");
        v.controls = true;
        v.src = p.src || "";
        if (p.poster) v.poster = p.poster;
        v.setAttribute("style", "width:100%;border-radius:12px;max-height:400px;background:#000;");
        wrap.appendChild(v);
        break;
      }
      case "hero": {
        const el = document.createElement("div");
        el.setAttribute(
          "style",
          styleStr({
            padding: p.padding,
            background: p.background,
            borderRadius: "16px",
            textAlign: "center",
          }),
        );
        el.innerHTML =
          "<h1 style='font-size:clamp(2rem,4vw,3rem);margin:0 0 12px;color:#fff;'>" +
          esc(p.title) +
          "</h1><p style='font-size:1.125rem;color:#94a3b8;max-width:560px;margin:0 auto;'>" +
          esc(p.subtitle) +
          "</p>";
        (block.children || []).forEach((ch) => el.appendChild(renderBlock(ch, options)));
        wrap.appendChild(el);
        break;
      }
      case "navbar": {
        const el = document.createElement("nav");
        el.setAttribute(
          "style",
          "display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;padding:16px 0;",
        );
        const links = (p.links || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean);
        el.innerHTML =
          "<strong style='color:#fff;font-size:1.1rem;'>" +
          esc(p.brand) +
          "</strong><div style='display:flex;gap:20px;flex-wrap:wrap;'>" +
          links
            .map(
              (l) =>
                "<span style='color:#94a3b8;font-size:0.9rem;'>" + esc(l) + "</span>",
            )
            .join("") +
          "</div>";
        wrap.appendChild(el);
        break;
      }
      case "footer": {
        const el = document.createElement("footer");
        el.setAttribute(
          "style",
          "padding:32px 0;border-top:1px solid rgba(148,163,184,0.2);text-align:center;color:#64748b;font-size:0.875rem;",
        );
        const links = (p.links || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean);
        el.innerHTML =
          "<p style='margin:0 0 12px;'>" +
          esc(p.text) +
          "</p><div>" +
          links.map((l) => "<span style='margin:0 8px;'>" + esc(l) + "</span>").join("") +
          "</div>";
        wrap.appendChild(el);
        break;
      }
      case "testimonials": {
        const el = document.createElement("blockquote");
        el.setAttribute(
          "style",
          "margin:0;padding:24px;border-radius:12px;background:rgba(255,255,255,0.04);border-left:4px solid #6366f1;color:#e2e8f0;",
        );
        el.innerHTML =
          "<p style='margin:0 0 8px;font-style:italic;'>\"" +
          esc(p.quote) +
          "\"</p><cite style='color:#94a3b8;font-size:0.875rem;'>— " +
          esc(p.author) +
          "</cite>";
        wrap.appendChild(el);
        break;
      }
      case "pricing": {
        const feats = (p.features || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean);
        const el = document.createElement("div");
        el.setAttribute(
          "style",
          "padding:24px;border-radius:16px;border:1px solid rgba(99,102,241,0.3);background:rgba(99,102,241,0.08);",
        );
        el.innerHTML =
          "<div style='font-size:0.75rem;text-transform:uppercase;color:#a5b4fc;font-weight:700;'>" +
          esc(p.plan) +
          "</div><div style='font-size:2rem;font-weight:800;color:#fff;margin:8px 0;'>" +
          esc(p.price) +
          "<span style='font-size:1rem;font-weight:500;color:#94a3b8;'>" +
          esc(p.period) +
          "</span></div><ul style='margin:16px 0;padding-left:20px;color:#94a3b8;font-size:0.9rem;'>" +
          feats.map((f) => "<li>" + esc(f) + "</li>").join("") +
          "</ul><span style='display:inline-block;padding:10px 20px;background:#6366f1;color:#fff;border-radius:8px;font-weight:600;'>" +
          esc(p.cta) +
          "</span>";
        wrap.appendChild(el);
        break;
      }
      case "faq": {
        const items = (p.items || "").split(";").filter(Boolean);
        const el = document.createElement("div");
        el.setAttribute("style", "display:flex;flex-direction:column;gap:8px;");
        items.forEach((pair) => {
          const [q, a] = pair.split("|").map((x) => x.trim());
          const row = document.createElement("details");
          row.setAttribute(
            "style",
            "border:1px solid rgba(148,163,184,0.2);border-radius:10px;padding:12px 16px;background:rgba(255,255,255,0.03);",
          );
          row.innerHTML =
            "<summary style='cursor:pointer;font-weight:600;color:#f1f5f9;'>" +
            esc(q || "?") +
            "</summary><p style='margin:8px 0 0;color:#94a3b8;font-size:0.9rem;'>" +
            esc(a || "") +
            "</p>";
          el.appendChild(row);
        });
        wrap.appendChild(el);
        break;
      }
      case "blogCards": {
        const el = document.createElement("div");
        el.innerHTML =
          "<h3 style='color:#fff;margin:0 0 8px;'>" +
          esc(p.title) +
          "</h3><p style='color:#64748b;margin:0 0 16px;'>" +
          esc(p.subtitle) +
          "</p><div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;'><div style='height:120px;border-radius:12px;background:rgba(255,255,255,0.06);'></div><div style='height:120px;border-radius:12px;background:rgba(255,255,255,0.06);'></div></div>";
        wrap.appendChild(el);
        break;
      }
      case "features": {
        const items = (p.items || "").split(";").filter(Boolean);
        const el = document.createElement("div");
        el.setAttribute("style", "display:grid;gap:16px;");
        items.forEach((pair) => {
          const [t, d] = pair.split("|").map((x) => x.trim());
          const row = document.createElement("div");
          row.setAttribute(
            "style",
            "display:flex;gap:12px;align-items:flex-start;padding:16px;border-radius:12px;background:rgba(255,255,255,0.04);",
          );
          row.innerHTML =
            "<span style='width:8px;height:8px;border-radius:50%;background:#22d3ee;margin-top:6px;flex-shrink:0;'></span><div><strong style='color:#f8fafc;'>" +
            esc(t || "") +
            "</strong><p style='margin:4px 0 0;color:#94a3b8;font-size:0.875rem;'>" +
            esc(d || "") +
            "</p></div>";
          el.appendChild(row);
        });
        wrap.appendChild(el);
        break;
      }
      case "input": {
        const inp = document.createElement("input");
        inp.type = p.inputType || "text";
        inp.placeholder = p.placeholder || "";
        inp.name = p.name || "";
        inp.setAttribute(
          "style",
          "width:100%;padding:12px 14px;border-radius:10px;border:1px solid rgba(148,163,184,0.25);background:rgba(0,0,0,0.2);color:#fff;",
        );
        wrap.appendChild(inp);
        break;
      }
      case "textarea": {
        const ta = document.createElement("textarea");
        ta.placeholder = p.placeholder || "";
        ta.name = p.name || "";
        ta.rows = p.rows || 4;
        ta.setAttribute(
          "style",
          "width:100%;padding:12px 14px;border-radius:10px;border:1px solid rgba(148,163,184,0.25);background:rgba(0,0,0,0.2);color:#fff;resize:vertical;",
        );
        wrap.appendChild(ta);
        break;
      }
      case "submit": {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = p.label || "Submit";
        btn.setAttribute(
          "style",
          "padding:12px 28px;border:none;border-radius:10px;background:linear-gradient(135deg,#6366f1,#4f46e5);color:#fff;font-weight:700;cursor:pointer;",
        );
        wrap.appendChild(btn);
        break;
      }
      default: {
        wrap.innerHTML = "<div style='color:#f87171;padding:8px;'>Unknown: " + esc(block.type) + "</div>";
      }
    }
    return wrap;
  }

  function walkBlocks(list, fn) {
    (list || []).forEach((b) => {
      fn(b);
      if (b.children && b.children.length) walkBlocks(b.children, fn);
    });
  }

  function getAboutPageTemplate() {
    const b = createBlock("richtext");
    b.props.html = ABOUT_PAGE_HTML;
    return [b];
  }

  function getBlogArticleTemplate() {
    const b = createBlock("richtext");
    b.props.html = BLOG_ARTICLE_HTML;
    return [b];
  }

  window.CmsBlocks = {
    uid,
    defaults,
    createBlock,
    renderBlock,
    walkBlocks,
    getAboutPageTemplate,
    getBlogArticleTemplate,
    palette: [
      { group: "Layout", types: ["section", "container", "grid", "column"] },
      { group: "Basic", types: ["heading", "paragraph", "richtext", "button", "image", "video"] },
      {
        group: "Advanced",
        types: ["hero", "navbar", "footer", "testimonials", "pricing", "faq", "blogCards", "features"],
      },
      { group: "Forms", types: ["input", "textarea", "submit"] },
    ],
  };
})();
