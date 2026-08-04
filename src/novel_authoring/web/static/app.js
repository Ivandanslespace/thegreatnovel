(function () {
  "use strict";

  const root = document.documentElement;
  const storedTheme = window.localStorage.getItem("novel-theme");
  if (storedTheme) root.dataset.theme = storedTheme;

  document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
    button.addEventListener("click", function () {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      window.localStorage.setItem("novel-theme", next);
    });
  });

  document.querySelectorAll("[data-chapter-search]").forEach(function (input) {
    input.addEventListener("input", function () {
      const query = input.value.trim().toLowerCase();
      document.querySelectorAll("[data-chapter-item]").forEach(function (item) {
        item.hidden = query !== "" && !item.textContent.toLowerCase().includes(query);
      });
    });
  });

  function openLatestChapter(bookId, editionId) {
    return fetch("/api/books/" + encodeURIComponent(bookId) + "/editions/" + encodeURIComponent(editionId) + "/chapters")
      .then(function (response) { return response.json(); })
      .then(function (chapters) {
        if (!chapters.length) return;
        window.location.href = "/books/" + encodeURIComponent(bookId) + "/editions/" + encodeURIComponent(editionId) + "/chapters/" + encodeURIComponent(chapters[chapters.length - 1].chapter_id);
      });
  }

  document.querySelectorAll("[data-edition-select]").forEach(function (select) {
    select.addEventListener("change", function () { openLatestChapter(select.dataset.bookId, select.value).catch(function () {}); });
  });
  document.querySelectorAll("[data-book-select]").forEach(function (select) {
    select.addEventListener("change", function () {
      fetch("/api/books/" + encodeURIComponent(select.value) + "/editions")
        .then(function (response) { return response.json(); })
        .then(function (editions) {
          const active = editions.find(function (edition) { return edition.status === "ACTIVE"; }) || editions[0];
          if (active) return openLatestChapter(select.value, active.edition_id);
          return undefined;
        })
        .catch(function () {});
    });
  });

  document.querySelectorAll("[data-view-tab]").forEach(function (tab) {
    tab.addEventListener("click", function () {
      const target = tab.dataset.viewTab;
      document.querySelectorAll("[data-view-tab]").forEach(function (item) { item.classList.toggle("active", item === tab); });
      document.querySelectorAll("[data-view-panel]").forEach(function (panel) { panel.hidden = panel.dataset.viewPanel !== target; });
    });
  });

  document.querySelectorAll("[data-segment-id]").forEach(function (segment) {
    segment.addEventListener("click", function () {
      document.querySelectorAll("[data-segment-id]").forEach(function (item) { item.classList.remove("selected"); });
      segment.classList.add("selected");
    });
  });

  document.querySelectorAll("[data-segment-link]").forEach(function (link) {
    link.addEventListener("click", function () {
      const segmentId = link.dataset.segmentLink;
      if (!segmentId) return;
      const target = document.getElementById("segment-" + segmentId);
      if (!target) return;
      document.querySelectorAll("[data-segment-id]").forEach(function (item) { item.classList.remove("selected"); });
      target.classList.add("selected");
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });

  document.querySelectorAll("[data-component-id]").forEach(function (chip) {
    chip.addEventListener("click", function () {
      document.querySelectorAll("[data-component-id]").forEach(function (item) { item.classList.remove("selected"); });
      chip.classList.add("selected");
      const card = chip.closest("[data-metric-id]");
      const componentKey = chip.dataset.componentId || "";
      const evidence = card && (card.querySelector('[data-evidence-component="' + CSS.escape(componentKey) + '"] [data-segment-link]') || card.querySelector("[data-segment-link]"));
      if (evidence) evidence.click();
      const observationId = chip.dataset.observationId;
      if (!observationId) return;
      const row = document.querySelector('[data-observation-row="' + CSS.escape(observationId) + '"]');
      if (row) row.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });

  document.querySelectorAll("[data-value-mirror]").forEach(function (slider) {
    const target = slider.parentElement && slider.parentElement.parentElement
      ? slider.parentElement.parentElement.querySelector("[data-value-target]")
      : null;
    if (!target) return;
    slider.addEventListener("input", function () { target.value = slider.value; });
    target.addEventListener("input", function () { slider.value = target.value; });
  });

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  document.querySelectorAll("form[data-api-form]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const formData = new FormData(form);
      const payload = {};
      formData.forEach(function (value, key) {
        if (key === "evidence_segment_ids") return;
        payload[key] = value;
      });
      const evidenceSegments = Array.from(form.querySelectorAll('[data-evidence-segment]:checked')).slice(0, 2);
      if (evidenceSegments.length) {
        payload.evidence_links = evidenceSegments.map(function (input) {
          return {
            segment_id: input.value,
            contribution_kind: "AUTHOR_EVIDENCE",
            direction: "SUPPORTS",
            confidence: 1,
            evidence_quote: input.dataset.quote || "",
            rationale: "作者在 Workbench 中选择的段落",
          };
        });
      }
      if (payload.value === "") payload.value = null;
      const valueInput = form.querySelector('[name="value"]');
      if (valueInput && (valueInput.type === "range" || valueInput.type === "number")) payload.value = Number(payload.value);
      fetch(form.action, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() }, body: JSON.stringify(payload) })
        .then(function (response) { return response.json().then(function (body) { return { ok: response.ok, body: body }; }); })
        .then(function (result) {
          const notice = document.createElement("p");
          notice.className = result.ok ? "callout" : "callout disputed";
          notice.textContent = result.ok ? "已保存；页面将重新加载当前审核状态。" : ((result.body.error && result.body.error.message) || "保存失败");
          form.appendChild(notice);
          if (result.ok) window.setTimeout(function () { window.location.reload(); }, 500);
        })
        .catch(function () { const notice = document.createElement("p"); notice.className = "callout disputed"; notice.textContent = "请求失败，请刷新后重试。"; form.appendChild(notice); });
    });
  });

  document.querySelectorAll("[data-copy-instruction]").forEach(function (button) {
    button.addEventListener("click", function () {
      fetch(button.dataset.copyInstruction)
        .then(function (response) { return response.json(); })
        .then(function (body) {
          const instruction = body.instruction || "";
          return navigator.clipboard.writeText(instruction).then(function () {
            button.textContent = "已复制";
            window.setTimeout(function () { button.textContent = "复制指令"; }, 1500);
          });
        })
        .catch(function () { button.textContent = "复制失败"; });
    });
  });
}());
