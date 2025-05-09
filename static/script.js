const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const chooseFileBtnInitial = document.getElementById('choose-file-btn-initial');
const chooseFileBtnConversion = document.getElementById('choose-file-btn-conversion');
const conversionOptions = document.getElementById('conversion-options');
const convertBtn = document.getElementById('convert-btn');
const toastContainer = document.getElementById('toast-container');
const formatOptions = document.querySelectorAll('.format-option');
const initialActions = document.getElementById('initial-actions');
const conversionActions = document.getElementById('conversion-actions');

let selectedFiles = [];
let selectedFormat = null;

document.addEventListener('DOMContentLoaded', () => {
  // Check if mobile
  const isMobile = window.innerWidth <= 768;
  
  if (window.IS_AUTH === false) {
    // Grey-out & intercept all "choose" / "convert" clicks
    [fileInput, chooseFileBtnInitial, chooseFileBtnConversion, convertBtn].forEach(el => {
      if (!el) return;
      el.disabled = true;
      el.addEventListener('click', e => {
        e.preventDefault();
        showToast("Please log in to convert files.", "error");
      });
    });
    // Stop here — don't bind any further handlers
    return;
  }
  
  // Drop & Choose file events
  if (dropZone) {
    dropZone.addEventListener('dragover', e => {
      e.preventDefault();
      dropZone.classList.add('dragging');
    });

    dropZone.addEventListener('dragleave', e => {
      e.preventDefault();
      dropZone.classList.remove('dragging');
    });

    dropZone.addEventListener('drop', handleDrop);
  }
  
  if (chooseFileBtnInitial) chooseFileBtnInitial.addEventListener('click', () => fileInput.click());
  if (chooseFileBtnConversion) chooseFileBtnConversion.addEventListener('click', () => fileInput.click());

  if (fileInput) {
    fileInput.addEventListener('change', handleFileChange);
  }

  function handleFileChange(e) {
    selectedFiles = Array.from(e.target.files);
    showPreviewAndOptions();
    toggleButtons();
  }

  function handleDrop(e) {
    e.preventDefault();
    dropZone.classList.remove('dragging');
    selectedFiles = Array.from(e.dataTransfer.files);
    showPreviewAndOptions();
    toggleButtons();
  }

  function toggleButtons() {
    if (initialActions) initialActions.style.display = 'none';
    if (conversionActions) conversionActions.style.display = 'flex';
    
    // On mobile, make sure buttons are full width and stacked
    if (isMobile && conversionActions) {
      conversionActions.style.flexDirection = 'column';
    }
  }

  function showPreviewAndOptions() {
    if (!selectedFiles || selectedFiles.length === 0) return;

    if (dropZone) dropZone.style.display = 'none';
    if (conversionOptions) conversionOptions.style.display = 'block';
    
    // Show conversion actions group
    if (conversionActions) conversionActions.style.display = 'flex';
    
    // Create image preview if it's an image
    const file = selectedFiles[0];
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = function(e) {
        const imagePreview = document.getElementById('image-preview');
        if (imagePreview) {
          imagePreview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
        }
      };
      reader.readAsDataURL(file);
    } else {
      // If not an image, just show the file name
      const imagePreview = document.getElementById('image-preview');
      if (imagePreview) {
        imagePreview.innerHTML = `<div class="file-name">${file.name}</div>`;
      }
    }

    showToast(`Selected ${selectedFiles.length} file(s)`, 'success');
  }

  formatOptions.forEach(btn => {
    btn.addEventListener('click', () => {
      selectedFormat = btn.dataset.format;
      formatOptions.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      showToast(`Selected format: ${selectedFormat.toUpperCase()}`, 'info');
    });
  });

  if (convertBtn) {
    convertBtn.addEventListener('click', () => {
      convertBtn.disabled = true;
      setTimeout(() => { convertBtn.disabled = false; }, 2000);
      
      if (selectedFiles.length === 0) {
        showToast("Please select files first", 'error');
        return;
      }
      if (!selectedFormat) {
        showToast("Please choose a format first", 'error');
        return;
      }

      const formData = new FormData();
      selectedFiles.forEach(file => formData.append('files', file));
      formData.append('format', selectedFormat);
      
      fetch('/convert', {
        method: 'POST',
        body: formData
      })
        .then(res => {
          if (!res.ok) {
            if (res.status === 401) {
              showToast("Please log in to convert files.", "error");
            } else if (res.status === 403) {
              showToast("You've reached your daily conversion limit.", "error");
            } else {
              showToast("Conversion failed.", "error");
            }
            throw new Error("Blocked by server");
          }
          return res.blob();
        })
        .then(blob => {
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `converted.${selectedFormat}`;
          a.click();
          showToast("Download started", 'success');
        })
        .catch(err => {
          console.error(err);
        });
    });
  }

  // Handle window resize event to apply mobile-specific styling
  window.addEventListener('resize', handleResize);
  
  // Initial call to set up responsive elements
  handleResize();
  
  function handleResize() {
    const isMobileView = window.innerWidth <= 768;
    
    // Apply mobile-specific styling
    if (isMobileView) {
      if (conversionActions && conversionActions.style.display !== 'none') {
        conversionActions.style.flexDirection = 'column';
      }
      
      // Make format buttons stack on mobile
      const formatButtons = document.querySelector('.format-buttons');
      if (formatButtons) {
        formatButtons.style.flexDirection = 'column';
      }
    } else {
      // Desktop styling
      if (conversionActions) {
        conversionActions.style.flexDirection = 'row';
      }
      
      const formatButtons = document.querySelector('.format-buttons');
      if (formatButtons) {
        formatButtons.style.flexDirection = 'row';
      }
    }
  }
});

// Toast messages
function showToast(message, type = 'info') {
  if (!toastContainer) return;
  
  const toast = document.createElement('div');
  toast.classList.add('toast', type);
  toast.textContent = message;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slide-out 0.3s ease-out forwards';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Highlight nav link if on profile
document.addEventListener('DOMContentLoaded', function () {
  const currentPage = window.location.pathname;
  if (currentPage.includes('profile')) {
    const myFilesLink = document.querySelector('.my-files a');
    if (myFilesLink) {
      myFilesLink.classList.add('active');
    }
  }
});

// FAQ accordion functionality
const faqItems = document.querySelectorAll('.faq-item');

if (faqItems.length > 0) {
  faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    const answer = item.querySelector('.faq-answer');

    if (question && answer) {
      question.addEventListener('click', () => {
        const isActive = item.classList.contains('active');

        // Collapse all other items
        faqItems.forEach(otherItem => {
          if (otherItem !== item) {
            otherItem.classList.remove('active');
            const otherAnswer = otherItem.querySelector('.faq-answer');
            if (otherAnswer) otherAnswer.style.height = '0px';
          }
        });

        // Toggle current item
        item.classList.toggle('active');

        if (!isActive) {
          answer.style.height = answer.scrollHeight + 'px';
        } else {
          answer.style.height = '0px';
        }
      });
    }
  });
}
