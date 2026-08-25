const $ = (s) => document.querySelector(s);

const state = { home: null, chapters: [], items: [], idx: 0, subjectId: null, sectionId: null, wrong: [], weekly: [], mode: "section" };

const api = {
  async get(url) {
    const r = await fetch(url);
    return r.json();
  },
  async post(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return r.json();
  },
};

function fmtAcc(a) {
  return a == null ? "—" : a + "%";
}

async function loadHome() {
  const data = await api.get("/api/home");
  state.home = data;
  const grid = $("#subjectGrid");
  grid.innerHTML = data.subjects
    .map((s) => {
      const pct = s.done ? Math.round((s.done / s.total) * 100) : 0;
      const accCls = s.accuracy == null ? "" : s.accuracy >= 70 ? "good" : "low";
      const icon = s.name.includes("线") ? "线" : "高";
      const chRows = s.chapters
        .map((c) => {
          const cPct = c.done ? Math.round((c.done / c.total) * 100) : 0;
          const cCls = c.accuracy == null ? "" : c.accuracy >= 70 ? "good" : "low";
          return `
          <div class="home-ch-row">
            <div class="home-ch-name">${c.title}</div>
            <div class="home-ch-bar"><div class="bar-fill ${cCls}" style="width:${cPct}%"></div></div>
            <div class="home-ch-acc ${cCls}">${fmtAcc(c.accuracy)}</div>
            <div class="home-ch-done">${c.done}/${c.total}</div>
          </div>`;
        })
        .join("");
      return `
      <div class="subject-card" data-sid="${s.id}">
        <div class="subject-icon">${icon}</div>
        <div class="subject-name">${s.name}</div>
        <div class="subject-stats">
          <span>总题 <b>${s.total}</b></span>
          <span>已做 <b>${s.done}</b></span>
          <span>错题 <b class="w">${s.wrong}</b></span>
        </div>
        <div class="subject-total-acc">
          <span>总正确率</span>
          <span class="subject-acc ${accCls}">${fmtAcc(s.accuracy)}</span>
          <div class="bar bar-total"><div class="bar-fill ${accCls}" style="width:${pct}%"></div></div>
        </div>
        <div class="home-ch-list">
          <div class="home-ch-head">各章正确率</div>
          ${chRows}
        </div>
      </div>`;
    })
    .join("");
  grid.querySelectorAll(".subject-card").forEach((el) =>
    el.addEventListener("click", () => {
      location.hash = "#/subject/" + el.dataset.sid;
    })
  );
}

function renderNav() {
  const nav = $("#chapterNav");
  nav.innerHTML = "";
  if (!state.home || !state.subjectId) return;
  for (const sub of state.home.subjects) {
    if (sub.id != state.subjectId) continue;
    state.chapters.forEach((c) => {
      const title = document.createElement("div");
      title.className = "nav-group-title";
      title.textContent = c.title;
      nav.appendChild(title);
      c.sections.forEach((s) => {
        const a = document.createElement("a");
        a.className = "nav-item nav-sec";
        a.href = "#/section/" + s.id;
        a.dataset.sid = s.id;
        a.innerHTML = `<span class="sec-dot"></span>${s.title}`;
        nav.appendChild(a);
      });
    });
  }
}

async function loadOverview(sid) {
  state.subjectId = sid;
  const data = await api.get("/api/overview?subject=" + sid);
  state.chapters = data.chapters;
  $("#ovTitle").textContent = data.subject;
  $("#ovSub").textContent = `共 ${data.total} 题`;
  $("#stTotal").textContent = data.total;
  $("#stDone").textContent = data.done;
  $("#stAccuracy").textContent = fmtAcc(data.accuracy);
  $("#stWrong").textContent = data.wrong;
  renderNav();
  const list = $("#chapterList");
  list.innerHTML = data.chapters
    .map((c) => {
      const pct = c.done ? Math.round((c.done / c.total) * 100) : 0;
      const accCls = c.accuracy == null ? "" : c.accuracy >= 70 ? "good" : "low";
      const secs = c.sections
        .map((s) => {
          const sPct = s.done ? Math.round((s.done / s.total) * 100) : 0;
          const sCls = s.accuracy == null ? "" : s.accuracy >= 70 ? "good" : "low";
          const chips = (s.questions || [])
            .map(
              (q) =>
                `<span class="q-chip ${q.status === "correct" ? "ok" : q.status === "wrong" ? "bad" : ""}" data-sid="${s.id}" data-num="${q.num}">${q.num}</span>`
            )
            .join("");
          return `
          <div class="sec-block" data-sid="${s.id}">
            <div class="sec-row">
              <div class="sec-name">${s.title}</div>
              <div class="sec-done">${s.done}/${s.total}</div>
              <div class="sec-acc ${sCls}">${fmtAcc(s.accuracy)}</div>
              <div class="sec-wrong ${s.wrong ? "has" : ""}">错 ${s.wrong}</div>
              <div class="bar sec-bar"><div class="bar-fill ${sCls}" style="width:${sPct}%"></div></div>
            </div>
            <div class="q-chips">${chips}</div>
          </div>`;
        })
        .join("");
      return `
      <div class="chapter-card">
        <div class="chapter-card-head">
          <div class="chapter-name"><span class="cn">第${c.num}章</span>${c.title.replace(/^第.章\s*/, "")}</div>
          <div class="chapter-stats">
            <span>已做 <b>${c.done}/${c.total}</b></span>
            <span>对 <b>${c.correct}</b></span>
            <span>错 <b>${c.wrong}</b></span>
            <span class="acc ${accCls}">${fmtAcc(c.accuracy)}</span>
          </div>
        </div>
        <div class="bar"><div class="bar-fill ${accCls}" style="width:${pct}%"></div></div>
        <div class="sec-list">${secs}</div>
      </div>`;
    })
    .join("");
  list.querySelectorAll(".q-chip").forEach((el) =>
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      location.hash = "#/section/" + el.dataset.sid + "?q=" + encodeURIComponent(el.dataset.num);
    })
  );
  list.querySelectorAll(".sec-row").forEach((el) =>
    el.addEventListener("click", () => {
      location.hash = "#/section/" + el.dataset.sid;
    })
  );
}

async function loadSection(sid) {
  state.mode = "section";
  state.sectionId = sid;
  state.items = await api.get("/api/section/" + sid);
  if (state.items.length) {
    const subj = state.items[0].subject_id;
    if (state.subjectId !== subj || !state.chapters.length) {
      await loadOverview(subj);
      renderNav();
    }
  }
  let ch = null;
  for (const c of state.chapters) {
    if (c.sections.some((x) => x.id == sid)) {
      ch = c;
      break;
    }
  }
  const s = state.chapters.flatMap((c) => c.sections).find((x) => x.id == sid);
  $("#chTitle").textContent = s ? s.title : "小节";
  $("#chSub").textContent = ch ? ch.title : "";
  renderQList();
  let first = -1;
  if (state.targetNum) {
    first = state.items.findIndex((q) => q.num === state.targetNum);
    state.targetNum = null;
  }
  if (first === -1) {
    first = state.items.findIndex((q) => q.status !== "correct");
  }
  state.idx = first === -1 ? 0 : first;
  renderQuestion();
}

function renderQList() {
  const list = $("#qList");
  list.innerHTML = state.items
    .map(
      (q, i) =>
        `<div class="q-list-item ${i === state.idx ? "current" : ""} ${
          q.status === "correct" ? "done" : q.status === "wrong" ? "wrong-done" : ""
        }" data-i="${i}">${q.num}</div>`
    )
    .join("");
  list.querySelectorAll(".q-list-item").forEach((el) =>
    el.addEventListener("click", () => {
      state.idx = +el.dataset.i;
      renderQuestion();
    })
  );
}

function renderQuestion() {
  const q = state.items[state.idx];
  if (!q) return;
  $("#qNum").textContent = `${q.num}（第 ${q.page} 页）`;
  $("#qImg").src = "/" + q.image;
  $("#qProgress").textContent = `${state.idx + 1} / ${state.items.length}`;
  $("#btnCorrect").classList.toggle("done-mark", q.status === "correct");
  renderQList();
}

async function setStatus(qid, status) {
  await api.post("/api/attempt", { question_id: qid, status });
  const q = state.items[state.idx];
  if (q) q.status = status;
  renderQuestion();
}

async function loadWeekly() {
  state.weekly = await api.get("/api/weekly");
  $("#weeklySub").textContent = `共 ${state.weekly.length} 套周测`;
  const list = $("#weeklyList");
  if (!state.weekly.length) {
    list.innerHTML = `<div class="empty-tip">还没有周测记录</div>`;
    return;
  }
  list.innerHTML = state.weekly
    .map((w) => {
      const pct = w.done ? Math.round((w.done / w.total) * 100) : 0;
      const accCls = w.accuracy == null ? "" : w.accuracy >= 70 ? "good" : "low";
      return `
      <div class="chapter-card" data-tid="${w.id}">
        <div class="chapter-card-head">
          <div class="chapter-name"><span class="cn">${w.date || ""}</span>${w.name}</div>
          <div class="chapter-stats">
            <span>已做 <b>${w.done}/${w.total}</b></span>
            <span>对 <b>${w.correct}</b></span>
            <span>错 <b>${w.wrong}</b></span>
            <span class="acc ${accCls}">${fmtAcc(w.accuracy)}</span>
          </div>
        </div>
        <div class="bar"><div class="bar-fill ${accCls}" style="width:${pct}%"></div></div>
      </div>`;
    })
    .join("");
  list.querySelectorAll(".chapter-card").forEach((el) =>
    el.addEventListener("click", () => {
      location.hash = "#/weekly/" + el.dataset.tid;
    })
  );
}

async function loadWeeklyTest(tid) {
  state.mode = "weekly";
  const data = await api.get("/api/weekly/" + tid);
  state.weeklyTest = data.test;
  state.items = data.items;
  $("#chTitle").textContent = data.test.name;
  $("#chSub").textContent = data.test.date || "";
  renderQList();
  let first = -1;
  if (state.targetNum) {
    first = state.items.findIndex((q) => q.num === state.targetNum);
    state.targetNum = null;
  }
  if (first === -1) {
    first = state.items.findIndex((q) => q.status !== "correct");
  }
  state.idx = first === -1 ? 0 : first;
  renderQuestion();
}

async function loadWrong() {
  state.wrong = await api.get("/api/wrong");
  $("#wrongSub").textContent = `共 ${state.wrong.length} 道错题`;
  const badge = $("#wrongBadge");
  badge.hidden = state.wrong.length === 0;
  badge.textContent = state.wrong.length;
  const grid = $("#wrongGrid");
  if (!state.wrong.length) {
    grid.innerHTML = `<div class="empty-tip">还没有错题，继续加油！</div>`;
    return;
  }
  grid.innerHTML = state.wrong
    .map(
      (w) => `
      <div class="wrong-card" data-i="${w.id}">
        <div class="wc-num">${w.weekly_name || w.subject_name} ${w.num}</div>
        <div class="wc-ch">${w.weekly_name ? w.weekly_name : w.section_title}</div>
        <div class="wc-date">${(w.updated_at || "").slice(0, 10)}</div>
      </div>`
    )
    .join("");
  grid.querySelectorAll(".wrong-card").forEach((el) =>
    el.addEventListener("click", () => openWrongModal(+el.dataset.i))
  );
}

let wrongCurrent = null;
function openWrongModal(qid) {
  wrongCurrent = state.wrong.find((w) => w.id === qid);
  if (!wrongCurrent) return;
  $("#wrongQNum").textContent = `${wrongCurrent.subject_name} ${wrongCurrent.num}（第 ${wrongCurrent.page} 页）`;
  $("#wrongQImg").src = "/" + wrongCurrent.image;
  $("#wrongModal").hidden = false;
}

function closeWrongModal() {
  $("#wrongModal").hidden = true;
  wrongCurrent = null;
}

async function wrongAction(status) {
  if (!wrongCurrent) return;
  await api.post("/api/attempt", { question_id: wrongCurrent.id, status });
  closeWrongModal();
  loadWrong();
}

function showView(name) {
  ["home", "overview", "section", "weekly", "wrong"].forEach((v) => {
    $(`#view-${v}`).hidden = v !== name;
  });
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
  let navEl;
  if (name === "home") {
    navEl = document.querySelector('[data-nav="home"]');
  } else if (name === "wrong") {
    navEl = document.querySelector('[data-nav="wrong"]');
  } else if (name === "weekly") {
    navEl = document.querySelector('[data-nav="weekly"]');
  } else {
    navEl = document.querySelector(`[data-sid="${state.sectionId}"]`);
  }
  if (navEl) navEl.classList.add("active");
}

async function route() {
  const h = location.hash || "#/";
  if (h === "#/" || h === "#/home") {
    state.subjectId = null;
    state.sectionId = null;
    showView("home");
    await loadHome();
    renderNav();
  } else if (h.startsWith("#/subject/")) {
    const sid = +h.split("/")[2];
    showView("overview");
    if (!state.home) await loadHome();
    await loadOverview(sid);
  } else if (h.startsWith("#/section/")) {
    const rest = h.split("/")[2];
    const qm = rest.indexOf("?q=");
    const sid = +(qm === -1 ? rest : rest.slice(0, qm));
    state.targetNum = qm === -1 ? null : decodeURIComponent(rest.slice(qm + 3));
    showView("section");
    if (!state.home) await loadHome();
    await loadSection(sid);
  } else if (h === "#/wrong") {
    showView("wrong");
    loadWrong();
  } else if (h === "#/weekly") {
    showView("weekly");
    loadWeekly();
  } else if (h.startsWith("#/weekly/")) {
    const rest = h.split("/")[2];
    const qm = rest.indexOf("?q=");
    const tid = +(qm === -1 ? rest : rest.slice(0, qm));
    state.targetNum = qm === -1 ? null : decodeURIComponent(rest.slice(qm + 3));
    showView("section");
    if (!state.home) await loadHome();
    await loadWeeklyTest(tid);
  }
}

window.addEventListener("hashchange", route);

$("#btnCorrect").addEventListener("click", () =>
  setStatus(state.items[state.idx].id, "correct")
);
$("#btnWrong").addEventListener("click", () =>
  setStatus(state.items[state.idx].id, "wrong")
);
$("#btnPrev").addEventListener("click", () => {
  if (state.idx > 0) {
    state.idx--;
    renderQuestion();
  }
});
$("#btnNext").addEventListener("click", () => {
  if (state.idx < state.items.length - 1) {
    state.idx++;
    renderQuestion();
  }
});
$("#wrongStillWrong").addEventListener("click", () => wrongAction("wrong"));
$("#wrongNowCorrect").addEventListener("click", () => wrongAction("correct"));
document.querySelectorAll("[data-close]").forEach((el) =>
  el.addEventListener("click", closeWrongModal)
);
document.querySelectorAll("[data-go]").forEach((el) =>
  el.addEventListener("click", () => {
    const target = el.dataset.go;
    if (target === "overview" && state.subjectId) {
      location.hash = "#/subject/" + state.subjectId;
    } else if (target === "overview" && state.mode === "weekly") {
      location.hash = "#/weekly";
    } else {
      location.hash = "#/";
    }
  })
);

$("#themeToggle").addEventListener("click", () => {
  const cur = document.documentElement.dataset.theme === "dark";
  document.documentElement.dataset.theme = cur ? "" : "dark";
  $("#themeToggle").textContent = cur ? "深色" : "浅色";
  localStorage.setItem("math-theme", cur ? "light" : "dark");
});

(function initTheme() {
  const t = localStorage.getItem("math-theme");
  if (t === "dark") {
    document.documentElement.dataset.theme = "dark";
    $("#themeToggle").textContent = "浅色";
  }
})();

route();
