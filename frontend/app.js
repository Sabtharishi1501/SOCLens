const dropzone = document.getElementById("dropzone");
const dropzoneText = document.getElementById("dropzone-text");
const fileInput = document.getElementById("file-input");
const runButton = document.getElementById("run-button");
const errorMessage = document.getElementById("error-message");

const uploadSection = document.getElementById("upload-section");
const loadingSection = document.getElementById("loading-section");
const loadingText = document.getElementById("loading-text");
const resultsSection = document.getElementById("results-section");
const resultsMeta = document.getElementById("results-meta");
const resultsList = document.getElementById("results-list");
const resetButton = document.getElementById("reset-button");

let selectedFile = null;

fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    setSelectedFile(fileInput.files[0]);
  }
});

["dragover", "dragenter"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);

["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);

dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) setSelectedFile(file);
});

function setSelectedFile(file) {
  selectedFile = file;
  dropzoneText.textContent = file.name;
  runButton.disabled = false;
  hideError();
}

runButton.addEventListener("click", async () => {
  if (!selectedFile) return;
  hideError();
  showLoading();

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    setLoadingStage("Reading the document…");

    const response = await fetch("/api/assess", {
      method: "POST",
      body: formData,
    });

    setLoadingStage("Scoring against the rubric…");

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "The assessment failed.");
    }

    renderResults(data);
  } catch (err) {
    showUploadPanel();
    showError(err.message || "Something went wrong. Please try again.");
  }
});

resetButton.addEventListener("click", () => {
  selectedFile = null;
  fileInput.value = "";
  dropzoneText.textContent = "Drop your SOP here, or choose a file";
  runButton.disabled = true;
  showUploadPanel();
});

function showLoading() {
  uploadSection.hidden = true;
  resultsSection.hidden = true;
  loadingSection.hidden = false;
}

function setLoadingStage(text) {
  loadingText.textContent = text;
}

function showUploadPanel() {
  uploadSection.hidden = false;
  loadingSection.hidden = true;
  resultsSection.hidden = true;
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function hideError() {
  errorMessage.hidden = true;
  errorMessage.textContent = "";
}

function tierFor(score) {
  if (score <= 1) return "tier-low";
  if (score <= 3) return "tier-mid";
  return "tier-high";
}

function renderResults(data) {
  loadingSection.hidden = true;
  resultsSection.hidden = false;

    const providerLabel =
      data.provider_used === "groq"
        ? "Groq"
        : data.provider_used === "mock"
        ? "Mock (no real analysis - MOCK_LLM is enabled)"
        : "Gemini (fallback)";
  let metaHtml = `
    <span class="filename">${escapeHtml(data.filename)}</span>
    <span>Scored by ${providerLabel}</span>
  `;

  if (data.truncated) {
    metaHtml += `<span>⚠ Document truncated to ${data.used_chars.toLocaleString()} of ${data.original_chars.toLocaleString()} characters</span>`;
  }

  resultsMeta.innerHTML = metaHtml;

  resultsList.innerHTML = data.results
    .map((r) => {
      const tier = tierFor(r.score);
      const verifiedTag = r.verified
        ? `<span class="verified-tag yes">✓ Evidence verified in document</span>`
        : `<span class="verified-tag no">⚠ Could not verify this quote against the document</span>`;

      return `
        <article class="finding ${tier}">
          <div class="finding-score">
            <span class="digit">${r.score}</span>
            <span class="out-of">/ 5</span>
          </div>
          <div class="finding-body">
            <h3>${escapeHtml(r.title)}</h3>
            <blockquote class="evidence">${escapeHtml(r.evidence)}</blockquote>
            <p class="explanation">${escapeHtml(r.explanation)}</p>
            <p class="gap"><strong>Gap:</strong> ${escapeHtml(r.gap)}</p>
            ${verifiedTag}
          </div>
        </article>
      `;
    })
    .join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}