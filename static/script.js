// === PLAN CONFIGURATION ===
// replace window.CURRENT_PLAN with your actual plan identifier if needed
const userPlan = window.CURRENT_PLAN || "free";
const planConfigs = {
  free: { maxFiles: 3,   maxSizeMB: 15,  batch: false },
  plus: { maxFiles: 15,  maxSizeMB: 30,  batch: true  },
  pro:  { maxFiles: 300, maxSizeMB: Infinity, batch: true }
};
const { maxFiles, maxSizeMB, batch } = planConfigs[userPlan];

// track how many conversions remain today
let remaining = 0, totalLimit = maxFiles;

async function fetchRemainingCount() {
  try {
    const res  = await fetch('/api/remaining_conversions');
    const data = await res.json();
    // take the server’s numbers instead of re-computing locally:
    const remEl = document.getElementById('remaining-count');
    remaining   = data.remaining;
    totalLimit  = data.limit;
    if (remEl) remEl.textContent = remaining;
  } catch (err) {
    console.error("Failed fetching remaining conversions:", err);
    // fallback to your local planConfigs if you really want:
    remaining = totalLimit; 
  }
}


document.addEventListener("DOMContentLoaded", async () => {
  await fetchRemainingCount();

  let selectedFiles = [];

  // ─── DOM references (match the new file-details section) ───────────
  const uploadSection      = document.getElementById("uploadSection");
  const addMoreSection     = document.getElementById("addMoreSection");
  const fileDetailsSection = document.getElementById("fileDetailsSection");

  const dropZone        = document.getElementById("uploadArea");
  const fileInput       = document.getElementById("fileInput");
  const chooseBtn       = document.querySelector(".upload-btn");
  const additionalInput = document.getElementById("additionalFileInput");
  const addFilesBtn     = document.querySelector(".add-more-btn");

  const fileList       = document.getElementById("fileList");
  const globalSelect   = document.getElementById("globalFormatSelect");
  const convertAllBtn  = document.getElementById("convertAllBtn");
  const fileCount      = document.getElementById("fileCount");
  const completedCount = document.getElementById("completedCount");
  const failedCount    = document.getElementById("failedCount");


  // open file dialogs
  chooseBtn.addEventListener("click", () => fileInput.click());
  addFilesBtn.addEventListener("click", () => additionalInput.click());

  // drag & drop
  dropZone.addEventListener("dragover", e => {
    e.preventDefault();
    dropZone.classList.add("dragging");
  });
  dropZone.addEventListener("dragleave", () =>
    dropZone.classList.remove("dragging")
  );
  dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("dragging");
    handleNewFiles(Array.from(e.dataTransfer.files));
  });

  // file selection
  fileInput.addEventListener("change", () => {
    handleNewFiles(Array.from(fileInput.files));
    fileInput.value = "";
  });
  additionalInput.addEventListener("change", () => {
    handleNewFiles(Array.from(additionalInput.files));
    additionalInput.value = "";
  });

globalSelect.addEventListener("change", () => {
  // copy its value into each file before you re-render
  selectedFiles.forEach(f => f.desiredFormat = globalSelect.value);
  renderFiles();
});

convertAllBtn.addEventListener("click", async () => {
  convertAllBtn.disabled    = true;
  convertAllBtn.textContent = "Please wait…";

  // gather all still-pending files
  const pending = selectedFiles
    .map((f, idx) => ({ f, idx }))
    .filter(({ f }) => f.status !== "completed");

  if (!pending.length) {
    convertAllBtn.disabled    = false;
    convertAllBtn.textContent = "Convert All";
    return;
  }

  if (batch) {
    // determine max parallelism per plan
    const concurrency = userPlan === "plus" ? 3
                       : userPlan === "pro"  ? 10
                       : 1;

    // process in chunks of [concurrency]
    for (let i = 0; i < pending.length; i += concurrency) {
      const slice = pending.slice(i, i + concurrency);
      // fire them all off in parallel, then wait for them all
      await Promise.all(
        slice.map(({ idx }) => convertFile(idx).catch(()=>{}))
      );
      renderFiles();
    }

  } else {
    // free tier: just one at a time
    await convertFile(pending[0].idx).catch(()=>{});
  }

  convertAllBtn.disabled    = false;
  convertAllBtn.textContent = "Convert All";
  renderFiles();
});



  // Handle newly added files (dragged or chosen)
  function handleNewFiles(files) {
    if (files.length > remaining) {
     showToast("Upload limit reached. Upgrade your plan or try again tomorrow.", "error");


      return;
    }
    files.forEach(file => {
      if (remaining <= 0 || selectedFiles.length >= maxFiles) return;
      const sizeMB = file.size / 1024 / 1024;
      if (sizeMB > maxSizeMB) return;
      selectedFiles.push(file);
      file.desiredFormat = globalSelect.value;   // or whatever your default is
file.status        = "ready";
file.progress      = 0;

      remaining--;
      const remEl = document.getElementById('remaining-count');
      if (remEl) remEl.textContent = remaining;
    });
    if (selectedFiles.length) {
      // hide the initial upload UI, show the file-details panel
      uploadSection.style.display      = "none";
      addMoreSection.style.display     = "block";
      fileDetailsSection.style.display = "block";
    }
  renderFiles();

    if (remaining <= 0 || selectedFiles.length >= maxFiles) {
      addFilesBtn.disabled = true;
      addFilesBtn.textContent = `Max ${remaining <= 0 ? totalLimit : maxFiles} files`;
    }
    dropZone.classList.toggle("has-files", selectedFiles.length > 0);
  }


function renderFiles() {
  // if no files: show upload panel again
  if (selectedFiles.length === 0) {
    fileDetailsSection.style.display = "none";
    uploadSection.style.display      = "block";
    addMoreSection.style.display     = "none";
    return;
  }

  fileDetailsSection.style.display = "block";
  uploadSection.style.display      = "none";
  addMoreSection.style.display     = "block";

  fileList.innerHTML = selectedFiles.map((file, idx) => {
    const sizeText  = (file.size/1024/1024).toFixed(1) + " MB";
    const status    = file.status || "ready";      // ready, uploading, converting, completed, error
    const progress  = file.progress || 0;           // 0–100
    const fmtOrig   = file.name.split('.').pop().toUpperCase();
    const fmtTarget = file.desiredFormat;
    // pick CSS class for status badge
    const statusClass = ({
      ready:      "uploaded",
      uploading:  "converting",
      converting: "converting",
      completed:  "completed",
      error:      "error"
    })[status];
    // pick icon SVG for badge (you can replace … with your SVG paths)
    const icons = {
      ready: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12,6 12,12 16,14"></polyline>
             </svg>`,
      uploading: `<svg class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">…</svg>`,
      converting:`<svg class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">…</svg>`,
      completed:`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10…"></path>
                    <polyline points="22,4 12,14.01 9,11.01"></polyline>
                 </svg>`,
      error:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="15" y1="9" x2="9" y2="15"></line>
                    <line x1="9" y1="9" x2="15" y2="15"></line>
                 </svg>`
    };
const statusText = status === "error"
  ? (file.errorMessage || "Failed")
  : ({
      ready:      "Ready",
      uploading:  "Uploading…",
      converting: "Converting…",
      completed:  "Completed"
    })[status];

    return `
      <div class="file-item" data-index="${idx}">
        <div class="file-content">
          <!-- Icon -->
          <div class="file-icon-container">
           <div class="file-icon">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
    <polyline points="14,2 14,8 20,8"></polyline>
  </svg>
</div>
          </div>

          <!-- Info -->
          <div class="file-info">
            <div class="file-header">
              <div class="file-main-info">
                <h3 class="file-name">${file.name}</h3>
                <div class="file-meta">
                  <div class="format-conversion">
                    <span class="original-format">${fmtOrig}</span>
                    <span class="arrow">→</span>
                    <span class="target-format">${fmtTarget}</span>
                  </div>
                  <span class="file-size">${sizeText}</span>
                </div>

                <!-- Progress bar -->
                ${(status==="uploading"||status==="converting")?`
                <div class="progress-container">
                  <div class="progress-header">
                    <span>${statusText}</span>
                    <span>${progress}%</span>
                  </div>
                  <div class="progress-bar">
                    <div class="progress-fill" style="width:${progress}%"></div>
                  </div>
                </div>`:""}

                <!-- Status badge & download -->
                <div class="status-actions">
                  <span class="status-badge ${statusClass}">
                    ${icons[status]}
                    <span>${statusText}</span>
                  </span>

              ${status==="completed" ? `
  <a href="${file.downloadUrl}" class="download-btn" download>Download</a>
` : ""}


                </div>
                 ${status==="error" ? `<div class="error-message">${file.errorMessage}</div>` : ""}
              </div>

              <!-- Per-file controls -->
              <div class="file-actions">
                ${status!=="completed"?`
                <select class="file-format-select"
                        onchange="updateFileFormat(${idx}, this.value)">
                  <option value="PNG"  ${fmtTarget==="PNG" ?"selected":""}>PNG</option>
                  <option value="JPG"  ${fmtTarget==="JPG" ?"selected":""}>JPG</option>
                  <option value="PDF"  ${fmtTarget==="PDF" ?"selected":""}>PDF</option>
                </select>`:""}
                <button class="action-btn remove"
                        onclick="removeFile(${idx})"
                        title="Remove file">
                 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="3,6 5,6 21,6"></polyline>
                                    <path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2V6"></path>
                                </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join("");

  // update footer counts
  fileCount.textContent      = `${selectedFiles.length} file${selectedFiles.length!==1?"s":""} ready`;
  completedCount.textContent = `${selectedFiles.filter(f=>f.status==="completed").length} completed`;
  failedCount.textContent    = `${selectedFiles.filter(f=>f.status==="error").length} failed`;
}

// hook helpers onto window so inline onclicks work:
window.removeFile = function(index) {
  selectedFiles.splice(index, 1);
  renderFiles();
};
window.updateFileFormat = function(index, format) {
  selectedFiles[index].desiredFormat = format;
  renderFiles();
};

/**
 * Show a one-line toast message.
 * @param {string} message – text to show
 * @param {'success'|'error'|'info'} [type='info']
 * @param {number} [duration=3000] – milliseconds before auto-dismiss
 */
function showToast(message, type = 'info', duration = 3000) {
  const container = document.getElementById('toast-container');
  const toast     = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  // trigger CSS animation
  requestAnimationFrame(() => toast.classList.add('show'));

  // remove after duration
  setTimeout(() => {
    toast.classList.remove('show');
    toast.addEventListener(
      'transitionend', 
      () => toast.remove(), 
      { once: true }
    );
  }, duration);
}

function convertFile(idx) {
  return new Promise((resolve, reject) => {
    const file = selectedFiles[idx];
    // mark as uploading
    file.status   = "uploading";
    file.progress = 0;
    renderFiles();

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/convert");
    xhr.responseType = "blob";

    // update progress on upload
    xhr.upload.onprogress = e => {
      file.status   = "uploading";
      file.progress = Math.round((e.loaded / e.total) * 100);
      renderFiles();
    };

    xhr.onload = () => {
      if (xhr.status === 200) {
        // build download URL
        const url = URL.createObjectURL(xhr.response);
        file.downloadUrl = url;
        file.status      = "completed";
        file.progress    = 100;
      } else {
    // ── error path ──
    file.status = "error";
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const obj = JSON.parse(reader.result);
        // backend might return { error:"…" } or { errors:[…] }
        file.errorMessage = obj.error || (obj.errors && obj.errors.join(", ")) || reader.result;
      } catch {
        file.errorMessage = reader.result || `HTTP ${xhr.status}`;
      }
      renderFiles();  // re-draw with the new message
    };
    reader.readAsText(xhr.response);
  }
      renderFiles();
      resolve();
    };

    xhr.onerror = () => {
      file.status = "error";
      file.errorMessage = "Network error";
      renderFiles();
      reject();
    };

    // send form data
    const fd = new FormData();
    fd.append("files", file);
    fd.append("format", file.desiredFormat);
    xhr.send(fd);
  });
}

});
