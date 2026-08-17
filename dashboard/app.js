const BUCKETS = [
  ["waiting", "Waiting"],
  ["silent", "Silent"],
  ["interview", "Interview"],
  ["offer", "Offer"],
  ["closed", "Closed"],
];

const STATUSES = [
  "applied",
  "interview",
  "offer",
  "hired",
  "rejected",
  "no_response",
  "offer_declined",
  "withdrawn",
  "interview_only",
];

async function load() {
  const res = await fetch("/api/state");
  const data = await res.json();
  render(data);
}

function render(data) {
  document.getElementById("empty").classList.toggle("hidden", !data.empty);
  const stats = document.getElementById("stats");
  const b = data.buckets;
  const c = data.backlog.counts;
  stats.innerHTML = [
    ["Waiting", b.waiting],
    ["Silent", b.silent],
    ["Interview", b.interview],
    ["Offer", b.offer],
    ["Closed", b.closed],
    ["New / ranked / expired", `${c.new} / ${c.ranked} / ${c.expired}`],
  ]
    .map(([label, value]) => `<div class="stat"><b>${value}</b><span>${label}</span></div>`)
    .join("");

  const board = document.getElementById("board");
  board.innerHTML = BUCKETS.map(([key, label]) => {
    const cards = data.applications
      .filter((app) => app.bucket === key)
      .map(cardHtml)
      .join("");
    return `<div class="column"><h3>${label}</h3>${cards || '<p class="meta">None</p>'}</div>`;
  }).join("");

  const ranked = data.backlog.ranked || [];
  const backlog = document.getElementById("backlog");
  if (!ranked.length) {
    backlog.innerHTML = `<p class="meta">${c.new ? `${c.new} new (run /rank in Claude)` : "No ranked jobs waiting."}</p>`;
  } else {
    backlog.innerHTML = `<table><thead><tr><th>Score</th><th>Role</th><th>Company</th><th>Gaps</th><th></th></tr></thead><tbody>${ranked
      .map((job) => {
        const cmd = job.url ? `/apply ${job.url}` : "/apply";
        const gaps = (job.rank_gaps || []).slice(0, 2).join("; ");
        return `<tr>
          <td>${job.rank_score ?? "—"}</td>
          <td>${esc(job.title)}</td>
          <td>${esc(job.company)}</td>
          <td>${esc(gaps)}</td>
          <td><button data-copy="${esc(cmd)}">Copy /apply</button></td>
        </tr>`;
      })
      .join("")}</tbody></table>`;
  }

  const portals = document.getElementById("portals");
  portals.innerHTML = (data.portals || [])
    .map(
      (p) => `<label class="portal ${p.enabled ? "" : "off"}">
        <input type="checkbox" data-portal="${esc(p.name)}" ${p.enabled ? "checked" : ""}>
        ${esc(p.name)}
      </label>`
    )
    .join("");

  board.querySelectorAll("[data-copy]").forEach(bindCopy);
  backlog.querySelectorAll("[data-copy]").forEach(bindCopy);
  board.querySelectorAll("select[data-status]").forEach((sel) => {
    sel.addEventListener("change", async () => {
      await fetch("/api/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company: sel.dataset.company,
          role: sel.dataset.role,
          status: sel.value,
        }),
      });
      load();
    });
  });
  portals.querySelectorAll("input[data-portal]").forEach((box) => {
    box.addEventListener("change", async () => {
      await fetch("/api/portals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: box.dataset.portal, enabled: box.checked }),
      });
      load();
    });
  });
}

function cardHtml(app) {
  const options = STATUSES.map(
    (s) => `<option value="${s}" ${s === app.status ? "selected" : ""}>${s}</option>`
  ).join("");
  const contact = app.archive && app.archive.contact ? app.archive.contact.name : app.contact_person;
  const links = [];
  if (app.cv_pdf) links.push(`<a href="/file?path=${encodeURIComponent(app.cv_pdf)}" target="_blank">CV PDF</a>`);
  if (app.cover_pdf) links.push(`<a href="/file?path=${encodeURIComponent(app.cover_pdf)}" target="_blank">Letter PDF</a>`);
  if (app.source) links.push(`<a href="${esc(app.source)}" target="_blank" rel="noopener">Posting</a>`);
  const cmds = app.commands || {};
  return `<article class="card ${app.bucket}">
    <h4>${esc(app.role)}</h4>
    <p class="meta">${esc(app.company)} · ${esc(app.date || "")}${contact ? ` · ${esc(contact)}` : ""}${app.fit_rating ? ` · fit ${esc(app.fit_rating)}` : ""}</p>
    <div class="row-actions">
      <select data-status data-company="${esc(app.company)}" data-role="${esc(app.role)}">${options}</select>
      <button data-copy="${esc(cmds.outcome || "")}">/outcome</button>
      <button data-copy="${esc(cmds.interview || "")}">/interview</button>
      <button data-copy="${esc(cmds.followup || "")}">--followup</button>
      ${links.join(" ")}
    </div>
  </article>`;
}

function bindCopy(btn) {
  btn.addEventListener("click", async () => {
    const text = btn.getAttribute("data-copy") || "";
    if (!text) return;
    await navigator.clipboard.writeText(text);
    const prev = btn.textContent;
    btn.textContent = "Copied";
    setTimeout(() => {
      btn.textContent = prev;
    }, 900);
  });
}

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

load();
