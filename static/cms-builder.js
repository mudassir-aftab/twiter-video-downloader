/**
 * CMS Admin — pages, builder, blog, media (API + Supabase)
 */
(function () {
  const API = "";
  const token = () => localStorage.getItem("admin_token");

  async function api(path, opts = {}) {
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    if (token()) headers["Authorization"] = "Bearer " + token();
    const res = await fetch(API + path, { ...opts, headers });
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { detail: text };
    }
    if (!res.ok) throw new Error(data.detail || res.statusText || "Request failed");
    return data;
  }

  const state = {
    view: "pages",
    pages: [],
    posts: [],
    media: [],
    currentPage: null,
    pageMeta: null,
    blocks: [],
    selectedId: null,
    history: [],
    historyIndex: -1,
    viewport: "desktop",
  };

  let quillEditor = null;

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  function toast(msg) {
    const t = $("#cms-toast");
    if (!t) return;
    t.textContent = msg;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 3200);
  }

  function pushHistory() {
    const snap = JSON.stringify(state.blocks);
    state.history = state.history.slice(0, state.historyIndex + 1);
    state.history.push(snap);
    state.historyIndex = state.history.length - 1;
    if (state.history.length > 50) {
      state.history.shift();
      state.historyIndex--;
    }
  }

  function undo() {
    if (state.historyIndex <= 0) return;
    state.historyIndex--;
    state.blocks = JSON.parse(state.history[state.historyIndex]);
    state.selectedId = null;
    renderCanvas();
    renderInspector();
  }

  function redo() {
    if (state.historyIndex >= state.history.length - 1) return;
    state.historyIndex++;
    state.blocks = JSON.parse(state.history[state.historyIndex]);
    state.selectedId = null;
    renderCanvas();
    renderInspector();
  }

  function findInTree(list, id) {
    for (let i = 0; i < list.length; i++) {
      if (list[i].id === id) return { list, index: i, block: list[i] };
      const ch = list[i].children;
      if (ch && ch.length) {
        const r = findInTree(ch, id);
        if (r) return r;
      }
    }
    return null;
  }

  function removeBlock(id) {
    const hit = findInTree(state.blocks, id);
    if (!hit) return;
    hit.list.splice(hit.index, 1);
    pushHistory();
    renderCanvas();
    if (state.selectedId === id) {
      state.selectedId = null;
      renderInspector();
    }
  }

  function duplicateBlock(id) {
    const hit = findInTree(state.blocks, id);
    if (!hit) return;
    const copy = JSON.parse(JSON.stringify(hit.block));
    const walk = (b) => {
      b.id = CmsBlocks.uid();
      if (b.children) b.children.forEach(walk);
    };
    walk(copy);
    hit.list.splice(hit.index + 1, 0, copy);
    pushHistory();
    renderCanvas();
    toast("Duplicated");
  }

  function addChildToSelected(type) {
    if (!state.selectedId || !CmsBlocks.createBlock) return;
    const hit = findInTree(state.blocks, state.selectedId);
    if (!hit) return;
    const b = hit.block;
    const allow = ["section", "container", "grid", "column", "hero", "navbar", "footer"];
    if (!allow.includes(b.type)) {
      toast("Select a layout block first");
      return;
    }
    if (!Array.isArray(b.children)) b.children = [];
    b.children.push(CmsBlocks.createBlock(type));
    pushHistory();
    renderCanvas();
  }

  function showView(name) {
    state.view = name;
    $$(".cms-nav-btn[data-view]").forEach((b) =>
      b.classList.toggle("active", b.dataset.view === name),
    );
    $$(".cms-view").forEach((v) => v.classList.toggle("active", v.id === "view-" + name));
    const titles = {
      pages: "Pages",
      builder: state.currentPage ? state.currentPage.title : "Builder",
      media: "Media Library",
      blog: "Blog",
      templates: "Templates",
      settings: "Settings",
    };
    const h = $("#cms-topbar-title");
    if (h) h.textContent = titles[name] || name;
    $("#cms-topbar-builder-actions").style.display =
      name === "builder" ? "flex" : "none";
    $("#cms-topbar-default-actions").style.display =
      name === "builder" ? "none" : "flex";
  }

  async function loadPages() {
    const tbody = $("#cms-pages-tbody");
    tbody.innerHTML =
      "<tr><td colspan='5'><div class='cms-skeleton'></div></td></tr>";
    try {
      const data = await api("/api/admin/cms/pages");
      state.pages = data.pages || [];
      renderPagesTable();
    } catch (e) {
      tbody.innerHTML =
        "<tr><td colspan='5' class='cms-empty'>" +
        esc(e.message) +
        "</td></tr>";
    }
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function renderPagesTable() {
    const tbody = $("#cms-pages-tbody");
    if (!state.pages.length) {
      tbody.innerHTML =
        "<tr><td colspan='5' class='cms-empty'>No pages yet. Create one.</td></tr>";
      return;
    }
    tbody.innerHTML = state.pages
      .map((p) => {
        const st = p.status === "published" ? "live" : "draft";
        const updated = (p.updated_at || "").slice(0, 16).replace("T", " ");
        return (
          "<tr><td><strong>" +
          esc(p.title) +
          "</strong></td><td><code>/" +
          esc(p.slug) +
          "</code></td><td><span class='cms-badge cms-badge-" +
          st +
          "'>" +
          esc(p.status) +
          "</span></td><td>" +
          esc(updated) +
          "</td><td class='cms-table-actions'><button type='button' class='cms-link-btn' data-edit='" +
          esc(p.id) +
          "'>Edit</button><button type='button' class='cms-link-btn' data-dup='" +
          esc(p.id) +
          "'>Duplicate</button><button type='button' class='cms-link-btn' style='color:#f87171' data-del='" +
          esc(p.id) +
          "'>Delete</button></td></tr>"
        );
      })
      .join("");

    tbody.querySelectorAll("[data-edit]").forEach((btn) => {
      btn.addEventListener("click", () => openBuilder(btn.dataset.edit));
    });
    tbody.querySelectorAll("[data-dup]").forEach((btn) => {
      btn.addEventListener("click", () => duplicatePage(btn.dataset.dup));
    });
    tbody.querySelectorAll("[data-del]").forEach((btn) => {
      btn.addEventListener("click", () => deletePage(btn.dataset.del));
    });
  }

  async function duplicatePage(id) {
    try {
      const data = await api("/api/admin/cms/pages/" + id + "/duplicate", {
        method: "POST",
      });
      toast("Duplicated");
      await loadPages();
    } catch (e) {
      toast(e.message);
    }
  }

  async function deletePage(id) {
    if (!confirm("Delete this page?")) return;
    try {
      await api("/api/admin/cms/pages/" + id, { method: "DELETE" });
      toast("Deleted");
      await loadPages();
    } catch (e) {
      toast(e.message);
    }
  }

  async function openBuilder(pageId) {
    try {
      const data = await api("/api/admin/cms/pages/" + pageId);
      state.currentPage = data.page;
      state.blocks = Array.isArray(data.page.blocks) ? data.page.blocks : [];
      const m = data.page.meta;
      state.pageMeta =
        m && typeof m === "object"
          ? { shell: true, theme: "light", ...m }
          : { shell: true, theme: "light" };
      if (state.pageMeta.shell === undefined) state.pageMeta.shell = true;
      state.selectedId = null;
      state.history = [JSON.stringify(state.blocks)];
      state.historyIndex = 0;
      showView("builder");
      renderCanvas();
      renderInspector();
      initSortable();
    } catch (e) {
      toast(e.message);
    }
  }

  let sortableInstance = null;
  function initSortable() {
    const inner = $("#cms-canvas-inner");
    if (!inner || typeof Sortable === "undefined") return;
    if (sortableInstance) {
      sortableInstance.destroy();
      sortableInstance = null;
    }
    if (inner.querySelectorAll(":scope > .cms-node").length === 0) return;
    sortableInstance = Sortable.create(inner, {
      animation: 180,
      draggable: "> .cms-node",
      onEnd: () => {
        const nodes = [...inner.querySelectorAll(":scope > .cms-node")];
        const order = nodes.map((n) => n.dataset.blockId).filter(Boolean);
        const map = new Map(state.blocks.map((b) => [b.id, b]));
        state.blocks = order.map((id) => map.get(id)).filter(Boolean);
        pushHistory();
      },
    });
  }

  function renderCanvas() {
    const inner = $("#cms-canvas-inner");
    if (!inner) return;
    inner.innerHTML = "";
    const opts = {
      editMode: true,
      selectedId: state.selectedId,
      onSelect: (id) => {
        state.selectedId = id;
        renderCanvas();
        renderInspector();
      },
    };
    state.blocks.forEach((b) => {
      inner.appendChild(CmsBlocks.renderBlock(b, opts));
    });
    if (!state.blocks.length) {
      inner.innerHTML =
        "<div class='cms-empty' style='min-height:200px;display:flex;align-items:center;justify-content:center;'>Drag components here</div>";
    }
  }

  function insertBlocksTemplate(kind) {
    if (!window.CmsBlocks || !state.currentPage) {
      toast("Open a page in the builder first");
      return;
    }
    const blocks =
      kind === "blog"
        ? CmsBlocks.getBlogArticleTemplate()
        : CmsBlocks.getAboutPageTemplate();
    state.blocks.push(...blocks);
    pushHistory();
    renderCanvas();
    initSortable();
    toast(kind === "blog" ? "Blog template inserted" : "About template inserted");
  }

  function renderInspector() {
    const panel = $("#cms-inspector-body");
    if (!panel) return;
    quillEditor = null;

    if (!state.selectedId) {
      if (!state.currentPage) {
        panel.innerHTML =
          "<p class='cms-empty' style='padding:0;'>Select a block or open a page.</p>";
        return;
      }
      const slug = state.currentPage.slug || "";
      const shellOn = state.pageMeta && state.pageMeta.shell !== false;
      panel.innerHTML =
        "<p class='cms-inspector-heading'>Page settings</p>" +
        "<div class='cms-field'><label class='cms-check'><input type='checkbox' id='cms-set-shell' " +
        (shellOn ? "checked" : "") +
        '> Marketing layout (header &amp; footer on live URL)</label></div>' +
        "<div class='cms-field'><span style='font-size:0.78rem;color:#64748b;line-height:1.5'>After <strong>Publish</strong>, open:<br><code>/p/" +
        esc(slug) +
        "</code> or <code>/pages/" +
        esc(slug) +
        "</code></span></div>" +
        "<p class='cms-inspector-heading' style='margin-top:16px'>Templates</p>" +
        "<div style='display:flex;flex-direction:column;gap:8px'>" +
        "<button type='button' class='cms-btn cms-btn-primary' id='cms-tpl-about'>Insert About-style block</button>" +
        "<button type='button' class='cms-btn' id='cms-tpl-blog'>Insert blog article block</button>" +
        "</div>" +
        "<p class='cms-empty' style='padding:16px 0 0;margin:0;font-size:0.82rem'>Drag <strong>Rich text</strong> from the left palette for an empty editor.</p>";
      const shellCb = $("#cms-set-shell");
      if (shellCb) {
        shellCb.addEventListener("change", () => {
          if (!state.pageMeta) state.pageMeta = {};
          state.pageMeta.shell = shellCb.checked;
        });
      }
      $("#cms-tpl-about")?.addEventListener("click", () => insertBlocksTemplate("about"));
      $("#cms-tpl-blog")?.addEventListener("click", () => insertBlocksTemplate("blog"));
      return;
    }
    const hit = findInTree(state.blocks, state.selectedId);
    if (!hit) {
      panel.innerHTML = "";
      return;
    }
    const b = hit.block;
    const p = b.props || {};
    let html = "";

    html +=
      "<div class='cms-field'><label>Type</label><input type='text' value='" +
      esc(b.type) +
      "' disabled></div>";

    if (b.type === "richtext") {
      html +=
        "<div class='cms-field'><label>Rich content</label><div id='cms-quill-wrap' class='cms-quill-mount'></div></div>";
    }

    const textKeys = ["text", "title", "subtitle", "label", "href", "src", "alt", "placeholder", "name", "brand", "links", "quote", "author", "plan", "price", "period", "features", "cta", "items", "content"];
    Object.keys(p).forEach((key) => {
      if (key === "html") return;
      if (key === "level" || key === "rows" || key === "inputType") return;
      const val = p[key];
      if (typeof val === "string" && textKeys.includes(key)) {
        const multiline = ["text", "content", "items", "features", "links"].includes(key);
        html +=
          "<div class='cms-field'><label>" +
          esc(key) +
          "</label>" +
          (multiline
            ? "<textarea data-prop='" +
              esc(key) +
              "'>" +
              esc(val) +
              "</textarea>"
            : "<input type='text' data-prop='" +
              esc(key) +
              "' value='" +
              esc(val) +
              "'>") +
          "</div>";
      }
    });

    if ("level" in p) {
      const lv = Number(p.level) || 2;
      html +=
        "<div class='cms-field'><label>Heading level</label><select data-prop='level'>" +
        [1, 2, 3, 4, 5, 6]
          .map(
            (n) =>
              "<option value='" + n + "'" + (lv === n ? " selected" : "") + ">" + n + "</option>",
          )
          .join("") +
        "</select></div>";
    }
    if ("fontSize" in p) {
      html +=
        "<div class='cms-field'><label>Font size</label><input type='text' data-prop='fontSize' value='" +
        esc(p.fontSize) +
        "'></div>";
    }
    if ("fontWeight" in p) {
      html +=
        "<div class='cms-field'><label>Font weight</label><input type='text' data-prop='fontWeight' value='" +
        esc(p.fontWeight) +
        "'></div>";
    }
    if ("color" in p) {
      html +=
        "<div class='cms-field'><label>Color</label><input type='color' data-prop-color='color' value='" +
        colorToHex(p.color) +
        "'><div class='cms-color-presets'><button type='button' data-cp='#f8fafc' style='background:#f8fafc'></button><button type='button' data-cp='#94a3b8' style='background:#94a3b8'></button><button type='button' data-cp='#6366f1' style='background:#6366f1'></button><button type='button' data-cp='#22d3ee' style='background:#22d3ee'></button></div></div>";
    }
    if ("textAlign" in p) {
      const cur = p.textAlign || "left";
      html +=
        "<div class='cms-field'><label>Align</label><select data-prop='textAlign'>" +
        ["left", "center", "right"]
          .map(
            (a) =>
              "<option value='" +
              a +
              "'" +
              (cur === a ? " selected" : "") +
              ">" +
              a +
              "</option>",
          )
          .join("") +
        "</select></div>";
    }
    if ("variant" in p) {
      const v = p.variant || "primary";
      html +=
        "<div class='cms-field'><label>Button style</label><select data-prop='variant'>" +
        ["primary", "outline", "ghost"]
          .map(
            (x) =>
              "<option value='" + x + "'" + (v === x ? " selected" : "") + ">" + x + "</option>",
          )
          .join("") +
        "</select></div>";
    }
    if ("width" in p && b.type === "image") {
      html +=
        "<div class='cms-field'><label>Width</label><input type='text' data-prop='width' value='" +
        esc(p.width) +
        "'></div>";
    }
    if ("borderRadius" in p) {
      html +=
        "<div class='cms-field'><label>Radius</label><input type='text' data-prop='borderRadius' value='" +
        esc(p.borderRadius) +
        "'></div>";
    }
    if ("padding" in p && typeof p.padding === "string") {
      html +=
        "<div class='cms-field'><label>Padding</label><input type='text' data-prop='padding' value='" +
        esc(p.padding) +
        "'></div>";
    }
    if ("background" in p && typeof p.background === "string") {
      html +=
        "<div class='cms-field'><label>Background</label><textarea data-prop='background'>" +
        esc(p.background) +
        "</textarea></div>";
    }

    html +=
      "<div class='cms-field'><label>Hidden</label><input type='checkbox' id='insp-hidden' " +
      (b.hidden ? "checked" : "") +
      "></div>";
    html +=
      "<div class='cms-field'><label>Locked</label><input type='checkbox' id='insp-locked' " +
      (b.locked ? "checked" : "") +
      "></div>";

    html +=
      "<div style='display:flex;flex-direction:column;gap:8px;margin-top:16px;'>" +
      "<button type='button' class='cms-btn cms-btn-primary' id='insp-dup-child'>Add child block…</button>" +
      "<select id='insp-child-type' class='cms-field' style='margin:0'><option value='heading'>heading</option><option value='paragraph'>paragraph</option><option value='richtext'>richtext</option><option value='button'>button</option><option value='image'>image</option></select>" +
      "<button type='button' class='cms-btn' id='insp-dup'>Duplicate block</button>" +
      "<button type='button' class='cms-btn' style='border-color:rgba(248,113,113,0.4);color:#f87171' id='insp-del'>Delete block</button></div>";

    panel.innerHTML = html;

    panel.querySelectorAll("[data-prop]").forEach((el) => {
      const ev = el.tagName === "SELECT" ? "change" : "input";
      el.addEventListener(ev, () => {
        const k = el.dataset.prop;
        let v = el.value;
        if (k === "level") v = parseInt(v, 10) || 2;
        hit.block.props[k] = v;
        renderCanvas();
      });
    });
    panel.querySelectorAll("[data-prop-color]").forEach((el) => {
      el.addEventListener("input", () => {
        hit.block.props.color = el.value;
        renderCanvas();
      });
    });
    panel.querySelectorAll("[data-cp]").forEach((btn) => {
      btn.addEventListener("click", () => {
        hit.block.props.color = btn.dataset.cp;
        renderCanvas();
        renderInspector();
      });
    });

    const h = $("#insp-hidden");
    if (h)
      h.addEventListener("change", () => {
        hit.block.hidden = h.checked;
        renderCanvas();
      });
    const l = $("#insp-locked");
    if (l)
      l.addEventListener("change", () => {
        hit.block.locked = l.checked;
        renderCanvas();
      });

    $("#insp-del")?.addEventListener("click", () => removeBlock(b.id));
    $("#insp-dup")?.addEventListener("click", () => duplicateBlock(b.id));
    $("#insp-dup-child")?.addEventListener("click", () => {
      const sel = $("#insp-child-type");
      addChildToSelected(sel ? sel.value : "paragraph");
    });

    if (b.type === "richtext" && window.Quill) {
      const mount = panel.querySelector("#cms-quill-wrap");
      if (mount) {
        const editorEl = document.createElement("div");
        mount.appendChild(editorEl);
        quillEditor = new Quill(editorEl, {
          theme: "snow",
          modules: {
            toolbar: [
              [{ header: [1, 2, 3, false] }],
              ["bold", "italic", "underline", "strike"],
              [{ list: "ordered" }, { list: "bullet" }],
              ["link", "blockquote", "clean"],
            ],
          },
        });
        quillEditor.root.innerHTML = p.html || "";
        let qt;
        quillEditor.on("text-change", () => {
          clearTimeout(qt);
          qt = setTimeout(() => {
            hit.block.props.html = quillEditor.root.innerHTML;
            renderCanvas();
          }, 350);
        });
      }
    }
  }

  function colorToHex(c) {
    if (!c || !c.startsWith("#")) return "#94a3b8";
    return c.length >= 7 ? c.slice(0, 7) : "#94a3b8";
  }

  async function saveDraft() {
    if (!state.currentPage) return;
    try {
      await api("/api/admin/cms/pages/" + state.currentPage.id, {
        method: "PATCH",
        body: JSON.stringify({ blocks: state.blocks, meta: state.pageMeta }),
      });
      toast("Draft saved");
    } catch (e) {
      toast(e.message);
    }
  }

  async function publishPage() {
    if (!state.currentPage) return;
    try {
      const res = await api("/api/admin/cms/pages/" + state.currentPage.id, {
        method: "PATCH",
        body: JSON.stringify({
          blocks: state.blocks,
          meta: state.pageMeta,
          status: "published",
        }),
      });
      if (res.page) {
        state.currentPage = res.page;
        const m = res.page.meta;
        if (m && typeof m === "object") {
          state.pageMeta = { shell: true, theme: "light", ...m };
        }
      } else {
        state.currentPage.status = "published";
      }
      const slug = state.currentPage.slug;
      toast("Published — /p/" + slug + " and /pages/" + slug);
      window.open("/p/" + encodeURIComponent(slug), "_blank");
    } catch (e) {
      toast(e.message);
    }
  }

  function openCreateModal() {
    $("#cms-modal-create").classList.add("open");
    $("#cms-new-title").value = "";
    $("#cms-new-slug").value = "";
  }

  function closeCreateModal() {
    $("#cms-modal-create").classList.remove("open");
  }

  function slugFromTitle(t) {
    return t
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "")
      .trim()
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-");
  }

  async function submitCreatePage() {
    const title = $("#cms-new-title").value.trim();
    let slug = $("#cms-new-slug").value.trim().replace(/^\//, "");
    if (!title) {
      toast("Enter a page name");
      return;
    }
    if (!slug) slug = slugFromTitle(title);
    try {
      const data = await api("/api/admin/cms/pages", {
        method: "POST",
        body: JSON.stringify({ title, slug, blocks: [], status: "draft" }),
      });
      closeCreateModal();
      toast("Page created");
      await loadPages();
      if (data.page) openBuilder(data.page.id);
    } catch (e) {
      toast(e.message);
    }
  }

  async function loadMedia() {
    const grid = $("#cms-media-grid");
    grid.innerHTML = "<div class='cms-skeleton' style='height:120px'></div>";
    try {
      const data = await api("/api/admin/cms/media");
      state.media = data.media || [];
      if (!state.media.length) {
        grid.innerHTML = "<div class='cms-empty'>No media. Upload an image.</div>";
        return;
      }
      grid.innerHTML = state.media
        .map(
          (m) =>
            "<div class='cms-media-tile' data-url='" +
            esc(m.url) +
            "'><img src='" +
            esc(m.url) +
            "' alt=''></div>",
        )
        .join("");
      grid.querySelectorAll(".cms-media-tile").forEach((tile) => {
        tile.addEventListener("click", () => {
          navigator.clipboard.writeText(tile.dataset.url);
          toast("Image URL copied");
        });
      });
    } catch (e) {
      grid.innerHTML = "<div class='cms-empty'>" + esc(e.message) + "</div>";
    }
  }

  function uploadMediaFile(file) {
    if (!file || !file.type.startsWith("image/")) {
      toast("Choose an image");
      return;
    }
    const r = new FileReader();
    r.onload = async () => {
      try {
        await api("/api/admin/cms/media", {
          method: "POST",
          body: JSON.stringify({
            filename: file.name,
            url: r.result,
            mime_type: file.type,
            file_size: file.size,
          }),
        });
        toast("Uploaded");
        loadMedia();
      } catch (e) {
        toast(e.message);
      }
    };
    r.readAsDataURL(file);
  }

  async function loadBlog() {
    const tbody = $("#cms-blog-tbody");
    tbody.innerHTML = "<tr><td colspan='4'><div class='cms-skeleton'></div></td></tr>";
    try {
      const data = await api("/api/admin/cms/blog");
      state.posts = data.posts || [];
      if (!state.posts.length) {
        tbody.innerHTML =
          "<tr><td colspan='4' class='cms-empty'>No posts yet.</td></tr>";
        return;
      }
      tbody.innerHTML = state.posts
        .map(
          (p) =>
            "<tr><td>" +
            esc(p.title) +
            "</td><td>/" +
            esc(p.slug) +
            "</td><td>" +
            esc(p.status) +
            "</td><td><button type='button' class='cms-link-btn' data-bed='" +
            esc(p.id) +
            "'>Edit</button> <button type='button' class='cms-link-btn' style='color:#f87171' data-bdel='" +
            esc(p.id) +
            "'>Del</button></td></tr>",
        )
        .join("");
      tbody.querySelectorAll("[data-bed]").forEach((btn) =>
        btn.addEventListener("click", () => openBlogModal(btn.dataset.bed)),
      );
      tbody.querySelectorAll("[data-bdel]").forEach((btn) =>
        btn.addEventListener("click", () => deleteBlog(btn.dataset.bdel)),
      );
    } catch (e) {
      tbody.innerHTML = "<tr><td colspan='4' class='cms-empty'>" + esc(e.message) + "</td></tr>";
    }
  }

  async function deleteBlog(id) {
    if (!confirm("Delete post?")) return;
    try {
      await api("/api/admin/cms/blog/" + id, { method: "DELETE" });
      toast("Deleted");
      loadBlog();
    } catch (e) {
      toast(e.message);
    }
  }

  function openBlogModal(postId) {
    const m = $("#cms-modal-blog");
    m.classList.add("open");
    const post = state.posts.find((p) => p.id === postId);
    $("#blog-edit-id").value = postId || "";
    $("#blog-title").value = post ? post.title : "";
    $("#blog-slug").value = post ? post.slug : "";
    $("#blog-content").value = post ? post.content : "";
    $("#blog-image").value = post ? post.featured_image_url || "" : "";
    $("#blog-status").value = post ? post.status : "draft";
  }

  function closeBlogModal() {
    $("#cms-modal-blog").classList.remove("open");
  }

  async function saveBlog() {
    const id = $("#blog-edit-id").value;
    const body = {
      title: $("#blog-title").value.trim(),
      slug: $("#blog-slug").value.trim().replace(/^\//, "") || slugFromTitle($("#blog-title").value),
      content: $("#blog-content").value,
      featured_image_url: $("#blog-image").value.trim() || null,
      status: $("#blog-status").value,
    };
    try {
      if (id) {
        await api("/api/admin/cms/blog/" + id, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      } else {
        await api("/api/admin/cms/blog", { method: "POST", body: JSON.stringify(body) });
      }
      closeBlogModal();
      toast("Blog saved");
      loadBlog();
    } catch (e) {
      toast(e.message);
    }
  }

  function buildPalette() {
    const pal = $("#cms-palette");
    if (!pal || !window.CmsBlocks) return;
    pal.innerHTML = "";
    CmsBlocks.palette.forEach((g) => {
      const h = document.createElement("h3");
      h.textContent = g.group;
      pal.appendChild(h);
      const wrap = document.createElement("div");
      wrap.className = "cms-palette-group";
      g.types.forEach((t) => {
        const el = document.createElement("div");
        el.className = "cms-palette-item";
        el.draggable = true;
        el.dataset.type = t;
        el.textContent = t
          .replace(/([A-Z])/g, " $1")
          .replace(/^./, (s) => s.toUpperCase())
          .trim();
        wrap.appendChild(el);
      });
      pal.appendChild(wrap);
    });
    $$(".cms-palette-item").forEach((item) => {
      item.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("application/cms-type", item.dataset.type);
        e.dataTransfer.effectAllowed = "copy";
      });
    });
  }

  function bind() {
    if (!token()) {
      window.location.href = "/admin/dashboard";
      return;
    }

    buildPalette();

    $$(".cms-nav-btn[data-view]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const v = btn.dataset.view;
        if (v === "builder" && !state.currentPage) {
          showView("pages");
          return;
        }
        showView(v);
        if (v === "pages") loadPages();
        if (v === "media") loadMedia();
        if (v === "blog") loadBlog();
      });
    });

    $("#cms-btn-new-page")?.addEventListener("click", openCreateModal);
    $("#cms-modal-close")?.addEventListener("click", closeCreateModal);
    $("#cms-modal-create-btn")?.addEventListener("click", submitCreatePage);
    $("#cms-new-title")?.addEventListener("input", () => {
      const s = $("#cms-new-slug");
      if (s && !s.dataset.touched) s.value = slugFromTitle($("#cms-new-title").value);
    });
    $("#cms-new-slug")?.addEventListener("input", () => {
      $("#cms-new-slug").dataset.touched = "1";
    });

    $("#cms-btn-save")?.addEventListener("click", saveDraft);
    $("#cms-btn-publish")?.addEventListener("click", publishPage);
    $("#cms-btn-preview")?.addEventListener("click", () => {
      if (state.currentPage)
        window.open("/p/" + encodeURIComponent(state.currentPage.slug), "_blank");
    });
    $("#cms-btn-back")?.addEventListener("click", () => {
      showView("pages");
      loadPages();
    });
    $("#cms-btn-undo")?.addEventListener("click", undo);
    $("#cms-btn-redo")?.addEventListener("click", redo);

    $$(".cms-viewport-toggle button").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$(".cms-viewport-toggle button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.viewport = btn.dataset.vp;
        const c = $("#cms-canvas");
        c.classList.remove("preview-tablet", "preview-mobile");
        if (state.viewport === "tablet") c.classList.add("preview-tablet");
        if (state.viewport === "mobile") c.classList.add("preview-mobile");
      });
    });

    const inner = $("#cms-canvas-inner");
    inner.addEventListener("dragover", (e) => {
      e.preventDefault();
      inner.classList.add("cms-drop-hover");
    });
    inner.addEventListener("dragleave", () => inner.classList.remove("cms-drop-hover"));
    inner.addEventListener("drop", (e) => {
      e.preventDefault();
      inner.classList.remove("cms-drop-hover");
      const type = e.dataTransfer.getData("application/cms-type");
      if (!type || !CmsBlocks.createBlock) return;
      state.blocks.push(CmsBlocks.createBlock(type));
      pushHistory();
      renderCanvas();
      initSortable();
    });

    $("#cms-media-file")?.addEventListener("change", (e) => {
      const f = e.target.files[0];
      if (f) uploadMediaFile(f);
      e.target.value = "";
    });

    $("#cms-btn-blog-new")?.addEventListener("click", () => {
      $("#blog-edit-id").value = "";
      $("#blog-title").value = "";
      $("#blog-slug").value = "";
      $("#blog-content").value = "";
      $("#blog-image").value = "";
      $("#blog-status").value = "draft";
      $("#cms-modal-blog").classList.add("open");
    });
    $("#cms-modal-blog-close")?.addEventListener("click", closeBlogModal);
    $("#cms-modal-blog-save")?.addEventListener("click", saveBlog);

    document.querySelectorAll(".cms-template-tile[data-template]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (state.view !== "builder" || !state.currentPage) {
          toast("Open a page in the builder first (Pages → Edit)");
          return;
        }
        insertBlocksTemplate(btn.dataset.template);
      });
    });

    showView("pages");
    loadPages();
  }

  document.addEventListener("DOMContentLoaded", bind);
})();
