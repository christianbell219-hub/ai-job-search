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

  renderNeeds(data.needs_action || []);
  renderRail(data.rail || [], data.gmail || {});
  renderInbox(data.paste_inbox || []);
  renderMarquee(data.portals || []);

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

  const expired = data.backlog.expired || [];
  const expiredEl = document.getElementById("expired");
  if (!expired.length) {
    expiredEl.innerHTML = "";
  } else {
    expiredEl.innerHTML = `<details>
      <summary>${expired.length} expired listings (ghost or deadline)</summary>
      <ul class="expired-list">${expired
        .map((job) => `<li>${esc(job.title)} · ${esc(job.company)}</li>`)
        .join("")}</ul>
    </details>`;
  }

  const portals = document.getElementById("portals");
  portals.innerHTML = (data.portals || [])
    .map(
      (p) => `<label class="portal ${p.enabled ? "" : "off"}">
        <span class="portal-name">${esc(p.name.replace(/-search$/, ""))}</span>
        <span class="portal-hint">${p.enabled ? "On for /scrape" : "Skipped"}</span>
        <input type="checkbox" data-portal="${esc(p.name)}" ${p.enabled ? "checked" : ""}>
      </label>`
    )
    .join("");

  board.querySelectorAll("select[data-status]").forEach((sel) => {
    sel.addEventListener("change", async () => {
      await postStatus(sel.dataset.company, sel.dataset.role, sel.value);
      load();
    });
  });
  board.querySelectorAll("button[data-submit]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      await postStatus(btn.dataset.company, btn.dataset.role, "applied");
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

function renderNeeds(actions) {
  const section = document.getElementById("needs");
  if (!actions.length) {
    section.innerHTML = `<div class="panel">
      <h2>Needs action</h2>
      <p class="hint">Nothing urgent. Copy /scrape when you want a fresh pass.</p>
    </div>`;
    return;
  }
  const items = actions
    .map((a) => {
      const who = [a.role, a.company].filter(Boolean).join(" · ");
      const label = (a.kind || "action").replace(/_/g, " ");
      return `<li class="needs-item">
        <span class="kind ${esc(a.kind)}">${esc(label)}</span>
        <span class="who">${esc(who)}</span>
        <p class="why">${esc(a.reason)}</p>
        <button type="button" data-copy="${esc(a.command)}">Copy</button>
      </li>`;
    })
    .join("");
  section.innerHTML = `<div class="panel">
    <h2>Needs action</h2>
    <p class="hint">Copy into Claude. This board does not draft or send mail.</p>
    <ul class="needs-list">${items}</ul>
  </div>`;
}

function renderRail(rail, gmail) {
  const el = document.getElementById("rail");
  el.innerHTML = rail
    .map(
      (item) => `<button type="button" class="rail-btn" data-copy="${esc(item.command)}">
        <b>${esc(item.label)}</b>
        <span>${esc(item.hint)}</span>
      </button>`
    )
    .join("");
  const stamp = document.getElementById("gmail-stamp");
  if (gmail.last_sync) {
    stamp.textContent = `Gmail last sync ${gmail.last_sync} · ${gmail.processed} messages seen`;
  } else {
    stamp.textContent = "Gmail sync has not run on this machine.";
  }
}

function renderInbox(items) {
  const el = document.getElementById("inbox");
  if (!items.length) {
    el.innerHTML = `<p class="meta">Empty. Paste a blocked posting as a .txt file, then copy /apply from here.</p>`;
    return;
  }
  el.innerHTML = `<ul class="inbox-list">${items
    .map(
      (item) => `<li>
        <a href="/file?path=${encodeURIComponent(item.path)}" target="_blank">${esc(item.name)}</a>
        <button type="button" data-copy="${esc(item.command)}">Copy apply</button>
      </li>`
    )
    .join("")}</ul>`;
}

function renderMarquee(portals) {
  const track = document.getElementById("marquee");
  const names = (portals.length ? portals : [{ name: "job search" }])
    .map((p) => p.name.replace(/-search$/, ""))
    .join(" · ");
  const line = `${names} · ${names} · `;
  track.textContent = line + line;
}

async function postStatus(company, role, status) {
  await fetch("/api/status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company, role, status }),
  });
}

function cardHtml(app, index) {
  const options = STATUSES.map(
    (s) => `<option value="${s}" ${s === app.status ? "selected" : ""}>${s}</option>`
  ).join("");
  const contactObj = app.archive && app.archive.contact ? app.archive.contact : {};
  const contact = contactObj.name || app.contact_person;
  const confidence = contactObj.confidence ? ` (${contactObj.confidence})` : "";
  const links = [];
  if (app.cv_pdf) links.push(`<a href="/file?path=${encodeURIComponent(app.cv_pdf)}" target="_blank">CV</a>`);
  if (app.cover_pdf) links.push(`<a href="/file?path=${encodeURIComponent(app.cover_pdf)}" target="_blank">Letter</a>`);
  if (app.source) links.push(`<a href="${esc(app.source)}" target="_blank" rel="noopener">Posting</a>`);
  const cmds = app.commands || {};
  const due =
    app.deadline_urgency === "past"
      ? `<span class="due-flag past">deadline passed</span>`
      : app.deadline_urgency === "soon"
        ? `<span class="due-flag">deadline soon</span>`
        : "";
  const age =
    app.status === "drafted" && app.days_open != null
      ? ` · drafted ${app.days_open}d`
      : app.days_open != null && app.bucket === "silent"
        ? ` · ${app.days_open}d quiet`
        : "";
  const submitBtn =
    app.status === "drafted"
      ? `<button type="button" data-submit data-company="${esc(app.company)}" data-role="${esc(app.role)}">Mark submitted</button>`
      : "";
  const pillLabel = app.status === "drafted" ? "drafted" : app.bucket;
  return `<div class="card-shell" style="--i:${index}">
    <article class="card ${app.bucket}">
      <span class="pill">${esc(pillLabel)}</span>${due}
      <h4>${esc(app.role)}</h4>
      <p class="meta">${esc(app.company)} · ${esc(app.date || "")}${age}${app.deadline ? ` · due ${esc(app.deadline)}` : ""}${contact ? ` · ${esc(contact)}${esc(confidence)}` : ""}${app.fit_rating ? ` · fit ${esc(app.fit_rating)}` : ""}</p>
      <div class="row-actions">
        <select data-status data-company="${esc(app.company)}" data-role="${esc(app.role)}" aria-label="Status for ${esc(app.company)}">${options}</select>
        ${submitBtn}
        <button type="button" data-copy="${esc(cmds.outcome || "")}">outcome</button>
        <button type="button" data-copy="${esc(cmds.interview || "")}">interview</button>
        <button type="button" data-copy="${esc(cmds.followup || "")}">follow-up</button>
        ${links.join(" ")}
      </div>
    </article>
  </div>`;
}

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

document.addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-copy]");
  if (!btn) return;
  const text = btn.getAttribute("data-copy") || "";
  if (!text) return;
  await navigator.clipboard.writeText(text);
  const prev = btn.innerHTML;
  btn.textContent = "Copied";
  setTimeout(() => {
    btn.innerHTML = prev;
  }, 900);
});

load();
