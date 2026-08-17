const BUCKETS = [
  ["waiting", "Waiting"],
  ["silent", "Silent"],
  ["interview", "Interview"],
  ["offer", "Offer"],
  ["closed", "Closed"],
];

const STATUSES = [
  "drafted",
  "applied",
  "interview",
  "offer",
  "hired",
  "rejected",
  "no_response",
  "offer_declined",
  "withdrawn",
];

async function load() {
  const res = await fetch("/api/state");
  const data = await res.json();
  render(data);
  document.body.classList.remove("is-loading");
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
    .map(([label, value]) => `<div class="metric"><b>${value}</b><span>${label}</span></div>`)
    .join("");

  const board = document.getElementById("board");
  board.innerHTML = BUCKETS.map(([key, label]) => {
    const items = data.applications.filter((app) => app.bucket === key);
    const cards = items.map((app, i) => cardHtml(app, i)).join("");
    return `<div class="column">
      <h3>${label} <b>${items.length}</b></h3>
      ${cards || '<p class="meta">None</p>'}
    </div>`;
  }).join("");

  const ranked = data.backlog.ranked || [];
  const backlog = document.getElementById("backlog");
  if (!ranked.length) {
    backlog.innerHTML = `<p class="meta">${c.new ? `${c.new} new. Run /rank in Claude.` : "No ranked jobs waiting."}</p>`;
  } else {
    backlog.innerHTML = `<table class="jobs"><thead><tr><th>Score</th><th>Role</th><th>Company</th><th>Gaps</th><th></th></tr></thead><tbody>${ranked
      .map((job) => {
        const cmd = job.url ? `/apply ${job.url}` : "/apply";
        const gaps = (job.gaps || job.rank_gaps || []).slice(0, 2).join("; ");
        return `<tr>
          <td class="num">${job.rank_score ?? "-"}</td>
          <td>${esc(job.title)}</td>
          <td>${esc(job.company)}</td>
          <td>${esc(gaps)}</td>
          <td><button type="button" data-copy="${esc(cmd)}">Copy apply</button></td>
        </tr>`;
      })
      .join("")}</tbody></table>`;
  }

  const portals = document.getElementById("portals");
  portals.innerHTML = (data.portals || [])
    .map(
      (p) => `<label class="portal ${p.enabled ? "" : "off"}">
        <input type="checkbox" data-portal="${esc(p.name)}" ${p.enabled ? "checked" : ""}>
        ${esc(p.name.replace(/-search$/, ""))}
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

function cardHtml(app, index) {
  const options = STATUSES.map(
    (s) => `<option value="${s}" ${s === app.status ? "selected" : ""}>${s}</option>`
  ).join("");
  const contact = app.archive && app.archive.contact ? app.archive.contact.name : app.contact_person;
  const links = [];
  if (app.cv_pdf) links.push(`<a href="/file?path=${encodeURIComponent(app.cv_pdf)}" target="_blank">CV</a>`);
  if (app.cover_pdf) links.push(`<a href="/file?path=${encodeURIComponent(app.cover_pdf)}" target="_blank">Letter</a>`);
  if (app.source) links.push(`<a href="${esc(app.source)}" target="_blank" rel="noopener">Posting</a>`);
  const cmds = app.commands || {};
  return `<div class="card-shell" style="--i:${index}">
    <article class="card ${app.bucket}">
      <span class="pill">${esc(app.bucket)}</span>
      <h4>${esc(app.role)}</h4>
      <p class="meta">${esc(app.company)} · ${esc(app.date || "")}${app.deadline ? ` · due ${esc(app.deadline)}` : ""}${contact ? ` · ${esc(contact)}` : ""}${app.fit_rating ? ` · fit ${esc(app.fit_rating)}` : ""}</p>
      <div class="row-actions">
        <select data-status data-company="${esc(app.company)}" data-role="${esc(app.role)}" aria-label="Status for ${esc(app.company)}">${options}</select>
        <button type="button" data-copy="${esc(cmds.outcome || "")}">outcome</button>
        <button type="button" data-copy="${esc(cmds.interview || "")}">interview</button>
        <button type="button" data-copy="${esc(cmds.followup || "")}">follow-up</button>
        ${links.join(" ")}
      </div>
    </article>
  </div>`;
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
