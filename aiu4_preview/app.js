// Responsibility: switch preview pages and show a privacy-safe example of per-paragraph bilingual reading.
const paragraphs = [
  { en: "A research system should make it easy to trace each answer back to the evidence that supports it.", zh: "研究系统应让人们能够轻松追溯每个回答背后的依据。" },
  { en: "When a paper is read in bilingual mode, each translated paragraph stays next to its English source.", zh: "阅读论文时选择中英对照模式后，每段译文都会紧跟对应的英文原文。" }
];
let mode = "original";

function renderParagraphs() {
  document.querySelectorAll("[data-paragraphs]").forEach((container) => {
    container.replaceChildren(...paragraphs.map((paragraph, index) => {
      const card = document.createElement("article");
      card.className = "pair";
      const sourceLabel = document.createElement("div");
      sourceLabel.className = "pair-label";
      sourceLabel.textContent = `EN · ENGLISH SOURCE · ${String(index + 1).padStart(2, "0")}`;
      const source = document.createElement("p");
      source.textContent = paragraph.en;
      card.append(sourceLabel, source);
      if (mode === "bilingual") {
        const translationLabel = document.createElement("div");
        translationLabel.className = "pair-label zh-label";
        translationLabel.textContent = "ZH · 中文翻译";
        const translation = document.createElement("p");
        translation.className = "zh";
        translation.textContent = paragraph.zh;
        card.append(translationLabel, translation);
      }
      return card;
    }));
  });
}

function setView(name) {
  const labels = { overview: "工作概览", discover: "在线找论文", library: "我的文献库" };
  document.querySelectorAll(".view").forEach((view) => {
    const active = view.id === name;
    view.hidden = !active;
    view.classList.toggle("active", active);
  });
  document.querySelectorAll("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
  document.querySelector("#breadcrumb").textContent = labels[name] || labels.overview;
  window.scrollTo(0, 0);
}

document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.go)));
document.querySelectorAll("[data-mode]").forEach((select) => select.addEventListener("change", () => {
  mode = select.value;
  document.querySelectorAll("[data-mode]").forEach((other) => { other.value = mode; });
  renderParagraphs();
}));
document.querySelectorAll("[data-translate]").forEach((button) => button.addEventListener("click", () => {
  mode = "bilingual";
  document.querySelectorAll("[data-mode]").forEach((select) => { select.value = mode; });
  renderParagraphs();
}));
renderParagraphs();
