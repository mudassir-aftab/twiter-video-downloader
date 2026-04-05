(function () {
  const el = document.getElementById("cms-bootstrap");
  const root = document.getElementById("cms-root");
  if (!el || !root || !window.CmsBlocks) return;
  try {
    const page = JSON.parse(el.textContent);
    document.title = page.title || "Page";
    const blocks = page.blocks || [];
    blocks.forEach((b) => {
      root.appendChild(
        window.CmsBlocks.renderBlock(b, { editMode: false }),
      );
    });
  } catch (e) {
    console.error(e);
    root.innerHTML = "<p style='color:#f87171;padding:24px;'>Could not render page.</p>";
  }
})();
