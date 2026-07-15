const screen = document.getElementById("screen");

const STAT_COLORS = {
  budget: "#4C9F70",
  reputation: "#4C7CC9",
  satisfaction: "#D9A441",
  morale: "#B75C9C",
  academic: "#C9564C",
};
const STAT_LABELS = {
  budget: "예산",
  reputation: "평판",
  satisfaction: "학생만족도",
  morale: "교사사기",
  academic: "학업성취도",
};

let principalName = "OO";
let currentEvent = null; // last fetched event, for rendering choice screen after result

async function api(path, body) {
  const opts = {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `요청 실패 (${res.status})`);
  }
  return data;
}

function el(tag, opts = {}, children = []) {
  const node = document.createElement(tag);
  if (opts.class) node.className = opts.class;
  if (opts.html !== undefined) node.innerHTML = opts.html;
  if (opts.text !== undefined) node.textContent = opts.text;
  if (opts.attrs) for (const [k, v] of Object.entries(opts.attrs)) node.setAttribute(k, v);
  if (opts.onclick) node.addEventListener("click", opts.onclick);
  children.forEach((c) => c && node.appendChild(c));
  return node;
}

function statBarBlock(state) {
  const card = el("div", { class: "card" });
  const header = el("div", {
    class: "status-header",
    text: `${state.month_label} · 서석고등학교 교장실 · ${principalName} 교장선생님`,
  });
  card.appendChild(header);
  ["budget", "reputation", "satisfaction", "morale", "academic"].forEach((key) => {
    const val = state[key];
    const row = el("div", { class: "stat-row" }, [
      el("div", { class: "stat-label-row" }, [
        el("span", { text: STAT_LABELS[key] }),
        el("span", { text: `${val}/100` }),
      ]),
      el("div", { class: "stat-bar-bg" }, [
        el("div", {
          class: "stat-bar-fill",
          attrs: { style: `width:${val}%; background:${STAT_COLORS[key]}` },
        }),
      ]),
    ]);
    card.appendChild(row);
  });
  return card;
}

function clearScreen() {
  screen.innerHTML = "";
}

function renderIntro() {
  clearScreen();
  const card = el("div", { class: "card" }, [
    el("h1", { text: "서석고등학교 교장 시뮬레이션" }),
    el("p", {
      class: "intro-desc",
      text: "3월 취임부터 다음해 2월 졸업식까지, 1개 학사년도 동안 예산·평판·학생만족도·교사사기·학업성취도 다섯 지표를 관리하며 학교를 이끌어야 합니다.",
    }),
    el("p", {
      class: "intro-desc",
      text: "제시된 선택지 외에도 직접 원하는 결정을 서술하면 그 내용대로 결과가 반영됩니다 (Gemini AI가 판정, 연결 실패 시 자동으로 키워드 판정으로 전환).",
    }),
  ]);

  const nameLabel = el("label", { class: "field-label", text: "취임하실 교장선생님의 성함을 입력해주세요:" });
  const nameInput = el("input", { attrs: { type: "text", placeholder: "예: 김민수" } });
  card.appendChild(nameLabel);
  card.appendChild(nameInput);

  const startBtn = el("button", { class: "btn-primary", text: "게임 시작", attrs: { style: "margin-top:14px;" } });
  card.appendChild(startBtn);

  const testRow = el("div", { attrs: { style: "margin-top:10px;" } });
  const testBtn = el("button", { class: "btn-secondary", text: "AI(Gemini) 연결 테스트" });
  const testStatus = el("div", { class: "status-msg" });
  testRow.appendChild(testBtn);
  testRow.appendChild(testStatus);
  card.appendChild(testRow);

  startBtn.addEventListener("click", async () => {
    startBtn.disabled = true;
    try {
      const data = await api("/api/start", { principal_name: nameInput.value.trim() });
      principalName = data.principal_name;
      currentEvent = data.event;
      renderEvent(data.state, data.event);
    } catch (e) {
      startBtn.disabled = false;
      alert("게임 시작 실패: " + e.message);
    }
  });

  testBtn.addEventListener("click", async () => {
    testStatus.textContent = "테스트 중...";
    testStatus.className = "status-msg pending";
    try {
      const data = await api("/api/test-gemini");
      testStatus.textContent = data.message;
      testStatus.className = "status-msg " + (data.ok ? "" : "error");
    } catch (e) {
      testStatus.textContent = "연결 테스트 실패: " + e.message;
      testStatus.className = "status-msg error";
    }
  });

  screen.appendChild(card);
}

function renderEvent(state, event) {
  clearScreen();
  screen.appendChild(statBarBlock(state));

  const card = el("div", { class: "card" });
  if (event.is_side) card.appendChild(el("span", { class: "tag-side", text: "돌발 이벤트" }));
  card.appendChild(el("h3", { text: event.title }));
  card.appendChild(el("p", { text: event.desc }));

  // --- 자유 답변(AI 판정) 섹션: 최상단, 강조 ---
  const aiBox = el("div", { class: "ai-box" });
  aiBox.appendChild(el("div", { class: "ai-badge", text: "🤖 AI 자유 판정 · 이 게임의 핵심" }));
  aiBox.appendChild(el("label", {
    class: "field-label ai-label",
    text: "교장으로서 어떻게 하시겠습니까? 원하는 대로 자유롭게 써보세요.",
  }));

  const textArea = el("textarea", {
    class: "ai-textarea",
    attrs: {
      rows: "3",
      placeholder: "예: 학부모 대표단과 원탁회의를 열어 함께 결정한다",
    },
  });
  aiBox.appendChild(textArea);

  const submitBtn = el("button", { class: "btn-ai", text: "✦ AI에게 판정받기" });
  const statusMsg = el("div", { class: "status-msg" });
  aiBox.appendChild(submitBtn);
  aiBox.appendChild(statusMsg);
  card.appendChild(aiBox);

  submitBtn.addEventListener("click", async () => {
    const text = textArea.value.trim();
    if (!text) {
      statusMsg.textContent = "문장을 입력한 뒤 눌러주세요.";
      statusMsg.className = "status-msg error";
      return;
    }
    card.querySelectorAll("button, textarea").forEach((b) => (b.disabled = true));
    statusMsg.textContent = "AI가 결정을 판정하는 중... (몇 초 걸릴 수 있어요)";
    statusMsg.className = "status-msg pending";
    try {
      const data = await api("/api/custom", { text });
      renderResult(data);
    } catch (e) {
      statusMsg.textContent = "판정 실패: " + e.message;
      statusMsg.className = "status-msg error";
      card.querySelectorAll("button, textarea").forEach((b) => (b.disabled = false));
    }
  });

  textArea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitBtn.click();
    }
  });

  // --- 정해진 선택지: 하단, 보조 옵션으로 톤다운 ---
  card.appendChild(el("hr", { class: "divider" }));
  card.appendChild(el("label", { class: "quick-choices-label", text: "또는, 빠른 선택지" }));

  event.choices.forEach((c) => {
    const btn = el("button", { class: "btn-choice-quiet", text: c.text });
    btn.addEventListener("click", async () => {
      card.querySelectorAll("button, textarea").forEach((b) => (b.disabled = true));
      try {
        const data = await api("/api/choice", { choice_index: c.index });
        renderResult(data);
      } catch (e) {
        alert("선택 처리 실패: " + e.message);
        card.querySelectorAll("button, textarea").forEach((b) => (b.disabled = false));
      }
    });
    card.appendChild(btn);
  });

  screen.appendChild(card);
}

function renderResult(data) {
  clearScreen();
  screen.appendChild(statBarBlock(data.state));

  const card = el("div", { class: "card" }, [
    el("p", { text: `→ ${data.result_text}` }),
  ]);

  if (data.reaction) {
    card.appendChild(el("div", { class: "reaction-box", html: data.reaction }));
  }

  if (data.game_over) {
    card.appendChild(el("h3", { class: "ending-title", text: `조기 종료 - ${data.game_over.title}` }));
    card.appendChild(el("p", { text: data.game_over.desc }));
    const restartBtn = el("button", { class: "btn-warn", text: "다시 시작", attrs: { style: "margin-top:10px;" } });
    restartBtn.addEventListener("click", restartGame);
    card.appendChild(restartBtn);
    screen.appendChild(card);
    return;
  }

  const nextBtn = el("button", { class: "btn-primary", text: "계속", attrs: { style: "margin-top:10px;" } });
  nextBtn.addEventListener("click", async () => {
    nextBtn.disabled = true;
    nextBtn.textContent = "다음 상황을 불러오는 중...";
    try {
      const next = await api("/api/next", {});
      if (next.ending) {
        renderEnding(next.state, next.ending);
      } else {
        renderEvent(next.state, next.event);
      }
    } catch (e) {
      alert("다음 진행 실패: " + e.message);
      nextBtn.disabled = false;
      nextBtn.textContent = "계속";
    }
  });
  card.appendChild(nextBtn);

  screen.appendChild(card);
}

function renderEnding(state, ending) {
  clearScreen();
  screen.appendChild(statBarBlock(state));

  const card = el("div", { class: "card" }, [
    el("h3", { class: "ending-title", text: `최종 엔딩 - ${ending.title}` }),
    el("p", { text: ending.desc }),
    el("p", {
      class: "ending-meta",
      text: `1년 평균 지표: ${ending.avg} / 100 · 가장 강점이었던 영역: ${ending.best} · 가장 아쉬웠던 영역: ${ending.worst}`,
    }),
  ]);
  const restartBtn = el("button", { class: "btn-warn", text: "다시 시작", attrs: { style: "margin-top:10px;" } });
  restartBtn.addEventListener("click", restartGame);
  card.appendChild(restartBtn);

  screen.appendChild(card);
}

async function restartGame() {
  try {
    await api("/api/restart", {});
  } catch (e) {
    /* ignore */
  }
  renderIntro();
}

renderIntro();
