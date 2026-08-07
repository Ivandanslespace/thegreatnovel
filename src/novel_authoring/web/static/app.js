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
    form.querySelectorAll('[data-innovation-auto]').forEach(function (auto) {
      auto.addEventListener("change", function () {
        if (!auto.checked) return;
        form.querySelectorAll('input[name="innovation_focus"]:not([data-innovation-auto])').forEach(function (item) {
          item.checked = false;
        });
      });
    });
    form.querySelectorAll('input[name="innovation_focus"]:not([data-innovation-auto])').forEach(function (item) {
      item.addEventListener("change", function () {
        if (item.checked) {
          const auto = form.querySelector('[data-innovation-auto]');
          if (auto) auto.checked = false;
        }
      });
    });
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const formData = new FormData(form);
      const payload = {};
      formData.forEach(function (value, key) {
        if (key === "evidence_segment_ids") return;
        if (key === "innovation_focus") {
          if (!Array.isArray(payload[key])) payload[key] = [];
          payload[key].push(String(value));
          return;
        }
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

  function atlasPathParts() {
    const parts = window.location.pathname.split("/").filter(Boolean);
    return { bookId: parts[1] || "", editionId: parts[3] || "" };
  }

  function atlasCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  function atlasAction(actionType, node, graphData) {
    const parts = atlasPathParts();
    const atlas = graphData.atlas || {};
    return fetch("/api/books/" + encodeURIComponent(parts.bookId) + "/editions/" + encodeURIComponent(parts.editionId) + "/atlas/actions", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": atlasCsrfToken() },
      body: JSON.stringify({
        action_type: actionType,
        target_id: node.node_id,
        payload: { target_type: node.node_type },
        expected_atlas_id: atlas.atlas_id || null,
        expected_atlas_version: atlas.atlas_version || null,
        expected_manifest_hash: atlas.artifact_manifest_sha256 || null,
      }),
    }).then(function (response) {
      return response.json().then(function (body) {
        if (!response.ok) throw new Error((body.error && body.error.message) || "作者操作失败");
        return body;
      });
    });
  }

  function showAtlasDetail(detail, node, graphData) {
    while (detail.firstChild) detail.removeChild(detail.firstChild);
    const heading = document.createElement("h2");
    heading.textContent = node.name || node.node_id;
    detail.appendChild(heading);
    const status = document.createElement("p");
    status.textContent = (node.information_status || "UNKNOWN") + " · " + (node.constraint_level || "") + " · " + (node.horizon || "") + " · confidence=" + (node.confidence || "UNKNOWN");
    detail.appendChild(status);
    const description = document.createElement("p");
    description.textContent = node.description || "当前没有额外说明。";
    detail.appendChild(description);
    const evidence = document.createElement("p");
    const evidenceData = node.evidence || {};
    const evidenceIds = [].concat(evidenceData.source_span_ids || [], evidenceData.chapter_ids || [], evidenceData.canon_fact_ids || [], evidenceData.event_ids || []);
    evidence.textContent = "Evidence: " + (evidenceIds.join(", ") || "UNKNOWN");
    detail.appendChild(evidence);
    const actions = document.createElement("div");
    actions.className = "actions";
    [
      ["ACCEPT_SOFT_ANCHOR", "接受 Soft Anchor"],
      ["REJECT_FUTURE_CANDIDATE", "拒绝 Future Candidate"],
      ["ADD_AUTHOR_INTENT", "标记 Author Intent"],
      ["ADD_REVIEW_QUEUE", "加入 Review Queue"],
    ].forEach(function (item) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button";
      button.textContent = item[1];
      button.addEventListener("click", function () {
        atlasAction(item[0], node, graphData).then(function () {
          button.textContent = "已记录";
          button.disabled = true;
        }).catch(function (error) { button.textContent = error.message; });
      });
      actions.appendChild(button);
    });
    detail.appendChild(actions);
  }

  document.querySelectorAll("[data-atlas-canvas]").forEach(function (svg) {
    let graphData;
    try { graphData = JSON.parse(svg.dataset.graph || "{}"); } catch (error) { return; }
    const nodes = graphData.nodes || [];
    const edges = graphData.edges || [];
    const width = 900;
    const height = Math.max(420, Math.ceil(nodes.length / 4) * 130);
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    const positions = {};
    nodes.forEach(function (node, index) {
      positions[node.node_id] = { x: 120 + (index % 4) * 220, y: 70 + Math.floor(index / 4) * 120 };
    });
    edges.forEach(function (edge) {
      const from = positions[edge.from_id];
      const to = positions[edge.to_id];
      if (!from || !to) return;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", from.x); line.setAttribute("y1", from.y);
      line.setAttribute("x2", to.x); line.setAttribute("y2", to.y);
      line.setAttribute("class", "atlas-edge " + String(edge.information_status || "unknown").toLowerCase());
      svg.appendChild(line);
    });
    const detail = document.querySelector("[data-atlas-detail]");
    nodes.forEach(function (node) {
      const position = positions[node.node_id];
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", "atlas-svg-node " + String(node.information_status || "unknown").toLowerCase());
      group.setAttribute("tabindex", "0");
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", position.x); circle.setAttribute("cy", position.y); circle.setAttribute("r", "24");
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", position.x); label.setAttribute("y", position.y + 46); label.setAttribute("text-anchor", "middle");
      label.textContent = node.name || node.node_id;
      group.appendChild(circle); group.appendChild(label); svg.appendChild(group);
      if (detail) {
        group.addEventListener("click", function () { showAtlasDetail(detail, node, graphData); });
        group.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") showAtlasDetail(detail, node, graphData); });
      }
    });
    document.querySelectorAll("[data-atlas-node]").forEach(function (card) {
      let node;
      try { node = JSON.parse(card.dataset.atlasNode || "{}"); } catch (error) { return; }
      card.addEventListener("click", function () { if (detail) showAtlasDetail(detail, node, graphData); });
    });
  });
}());
