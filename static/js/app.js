const money = value => value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const palette = categories => {
  const canvas = document.querySelector(".spend canvas");
  if (!canvas) return;
  const context = canvas.getContext("2d");
  if (!context) return;
  const box = canvas.getBoundingClientRect(), scale = window.devicePixelRatio || 1;
  const size = Math.min(box.width, box.height);
  canvas.width = size * scale; canvas.height = size * scale;
  context.setTransform(scale, 0, 0, scale, 0, 0);
  const total = categories.reduce((sum, item) => sum + item.amount, 0);
  let angle = -Math.PI / 2;
  categories.forEach(item => {
    const end = angle + (total ? item.amount / total : 0) * Math.PI * 2;
    context.beginPath(); context.moveTo(size / 2, size / 2); context.arc(size / 2, size / 2, size / 2, angle, end); context.closePath();
    context.fillStyle = item.color; context.fill(); angle = end;
  });
  if (!categories.length) { context.beginPath(); context.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2); context.fillStyle = "#e5e7eb"; context.fill(); }
};

const dropdown = document.getElementById("catDropdown");
if (dropdown) {
  const summary = document.getElementById("catSummary"), all = document.getElementById("catSelectAll");
  const boxes = [...dropdown.querySelectorAll(".cat-cb")];
  const sync = () => {
    const checked = boxes.filter(box => box.checked);
    summary.textContent = !checked.length ? "None selected" : checked.length === boxes.length ? `All (${checked.length})` : checked.length === 1 ? checked[0].parentElement.textContent.trim() : `${checked.length} selected`;
    all.checked = boxes.length > 0 && checked.length === boxes.length;
    all.indeterminate = checked.length > 0 && checked.length < boxes.length;
  };
  all.addEventListener("change", () => { boxes.forEach(box => { box.checked = all.checked; }); sync(); });
  boxes.forEach(box => box.addEventListener("change", sync));
  document.addEventListener("click", event => { if (!dropdown.contains(event.target)) dropdown.removeAttribute("open"); });
  sync();
}

const spend = document.querySelector(".spend");
if (spend) {
  const form = document.querySelector('form.filters input[name="month"]').form;
  const entries = [...document.querySelectorAll(".legend li")].map(entry => ({
    name: entry.textContent.split(":")[0],
    amount: Number(entry.textContent.match(/\$([\d,]+(?:\.\d+)?)/)?.[1].replaceAll(",", "") || 0),
    color: getComputedStyle(entry.querySelector(".swatch")).backgroundColor,
  }));
  const pie = () => palette(entries);
  pie(); window.addEventListener("resize", pie);
  const refreshSpend = async () => {
    const url = new URL(spend.dataset.spendUrl, location.href), params = new URLSearchParams();
    new FormData(form).forEach((value, key) => { if (typeof value === "string") params.append(key, value); });
    url.search = params.toString();
    const response = await fetch(url);
    if (!response.ok) throw new Error("Could not refresh spending chart");
    const data = await response.json();
    spend.querySelector(".spend-total").textContent = `Total spend: $${money(data.total)}`;
    let list = spend.querySelector(".legend"), empty = spend.querySelector(".muted");
    if (data.breakdown.length) {
      if (!list) { list = document.createElement("ul"); list.className = "legend"; empty?.replaceWith(list); }
      list.replaceChildren(...data.breakdown.map(item => {
        const li = document.createElement("li"), swatch = document.createElement("span"), label = document.createElement("span");
        swatch.className = "swatch"; swatch.style.backgroundColor = item.color;
        label.textContent = `${item.name}: $${money(item.amount)} (${item.percent.toFixed(1)}%)`; li.append(swatch, label); return li;
      }));
    } else if (!empty) { empty = document.createElement("p"); empty.className = "muted"; empty.textContent = "No spending found for this period."; list?.replaceWith(empty); }
    palette(data.breakdown);
  };
  document.querySelectorAll(".category-form, .reset-form").forEach(form => {
    form.querySelector('select[name="category_id"]')?.addEventListener("change", () => form.requestSubmit());
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const row = form.closest("tr"), select = form.querySelector('select[name="category_id"]');
      try {
        const response = await fetch(form.action, { method: "POST", headers: { "X-Requested-With": "fetch" }, body: new FormData(form) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Update failed");
        row.querySelector(".manual")?.remove();
        if (data.manual) { const badge = document.createElement("span"); badge.className = "manual"; badge.title = "Manually categorized"; badge.textContent = "Manual"; row.querySelector(".category-form").append(" ", badge); }
        const reset = row.querySelector(".reset-form"); if (reset) reset.style.display = data.manual ? "inline" : "none";
        const category = new URLSearchParams(location.search).get("category_id");
        if (category && (category === "uncategorized" ? data.category_id !== null : String(data.category_id) !== category)) row.remove();
        if (!row.isConnected) {
          const count = document.querySelector("body > p.muted");
          if (count) { const current = Number(count.textContent.match(/\d+/)?.[0] || 0); count.textContent = `${Math.max(0, current - 1)} transaction${current === 2 ? "" : "s"}`; }
          if (!document.querySelector("tbody tr")) document.querySelector("tbody").innerHTML = '<tr><td colspan="6">No transactions match these filters.</td></tr>';
        }
        await refreshSpend();
      } catch (error) { window.alert(error instanceof Error ? error.message : "Could not update category."); }
    });
  });
}

const canvas = document.getElementById("net-worth-chart"), trendUrl = canvas?.dataset.trendUrl;
if (canvas && trendUrl) fetch(trendUrl).then(response => response.json()).then(data => {
  const ctx = canvas.getContext("2d"); if (!ctx || !data.length) return;
  const draw = () => {
    const box = canvas.getBoundingClientRect(), scale = window.devicePixelRatio || 1;
    canvas.width = box.width * scale; canvas.height = box.height * scale; ctx.setTransform(scale, 0, 0, scale, 0, 0);
    const w = box.width, h = box.height, pad = { l: 60, r: 12, t: 14, b: 34 }, values = data.map(point => point.amount);
    const min = Math.min(...values), max = Math.max(...values), span = max - min || Math.max(Math.abs(max) * .1, 1);
    const x = i => pad.l + (data.length === 1 ? (w - pad.l - pad.r) / 2 : i * (w - pad.l - pad.r) / (data.length - 1));
    const y = v => pad.t + (max - v + span * .08) * (h - pad.t - pad.b) / (span * 1.16);
    ctx.clearRect(0, 0, w, h); ctx.font = "10px DM Mono, monospace"; ctx.fillStyle = "#6b6760"; ctx.strokeStyle = "#d4cfc6";
    for (let i = 0; i < 4; i++) { const value = min + span * i / 3, yy = y(value); ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(w - pad.r, yy); ctx.stroke(); ctx.textAlign = "right"; ctx.fillText(`$${Math.round(value).toLocaleString()}`, pad.l - 8, yy + 3); }
    ctx.beginPath(); data.forEach((point, i) => i ? ctx.lineTo(x(i), y(point.amount)) : ctx.moveTo(x(i), y(point.amount))); ctx.strokeStyle = "#2c5f8a"; ctx.lineWidth = 2; ctx.stroke();
    data.forEach((point, i) => { ctx.beginPath(); ctx.arc(x(i), y(point.amount), 3, 0, Math.PI * 2); ctx.fillStyle = "#2c5f8a"; ctx.fill(); if (i === 0 || i === data.length - 1 || data.length < 7) { ctx.fillStyle = "#6b6760"; ctx.textAlign = i === 0 ? "left" : i === data.length - 1 ? "right" : "center"; ctx.fillText(point.date, x(i), h - 10); } });
  };
  draw(); window.addEventListener("resize", draw);
});
