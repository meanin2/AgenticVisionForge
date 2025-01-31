// static/scripts.js

//
// 1. Global Alpine.js setup for Dark Mode (already in base.html's x-init),
//    so we primarily keep our own JS here for other functionality.
//
// 2. showToast (unified toast function).
//

function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;
  
    const toast = document.createElement('div');
    toast.className = `toast fixed bottom-5 right-5 p-4 rounded-lg shadow-lg text-white ${
      type === 'error'
        ? 'bg-red-500'
        : type === 'success'
        ? 'bg-green-500'
        : 'bg-blue-500'
    }`;
    toast.textContent = message;
  
    container.appendChild(toast);
  
    setTimeout(() => {
      toast.remove();
    }, duration);
  }
  
  //
  // 3. Utility: file upload for drag-and-drop or direct selection
  //
  async function uploadFile(file, uploadEndpoint = '/upload') {
    const formData = new FormData();
    formData.append('file', file);
  
    try {
      const response = await fetch(uploadEndpoint, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Error uploading file');
      }
      showToast(data.message || 'File uploaded successfully!', 'success');
    } catch (error) {
      showToast('Error uploading file: ' + error.message, 'error');
    }
  }
  
  function initDragDropZone(selector = '.drop-zone', uploadEndpoint = '/upload') {
    const dropZone = document.querySelector(selector);
    if (!dropZone) return;
  
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
      dropZone.addEventListener(eventName, preventDefaults, false);
    });
  
    function preventDefaults(e) {
      e.preventDefault();
      e.stopPropagation();
    }
  
    ['dragenter', 'dragover'].forEach((eventName) => {
      dropZone.addEventListener(eventName, () => highlight(true), false);
    });
    ['dragleave', 'drop'].forEach((eventName) => {
      dropZone.addEventListener(eventName, () => highlight(false), false);
    });
  
    function highlight(on) {
      if (on) {
        dropZone.classList.add('border-blue-500');
      } else {
        dropZone.classList.remove('border-blue-500');
      }
    }
  
    dropZone.addEventListener('drop', handleDrop, false);
  
    function handleDrop(e) {
      const dt = e.dataTransfer;
      const files = dt.files;
      handleFiles(files);
    }
  
    function handleFiles(files) {
      [...files].forEach((file) => {
        uploadFile(file, uploadEndpoint);
      });
    }
  }
  
  //
  // 4. Index Page ("/" => data-page="index"):
  //    - Handle "Create Run" form submission
  //    - Show a modal for confirm delete (if present).
  //
  
  function initIndexPage() {
    const form = document.getElementById('create-run-form');
    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitButton = form.querySelector('button[type="submit"]');
        const submitSpinner = document.getElementById('submit-spinner');
        const submitText = document.getElementById('submit-text');
  
        // Disable form / show spinner
        submitButton.disabled = true;
        if (submitSpinner) submitSpinner.classList.remove('hidden');
        if (submitText) submitText.textContent = 'Creating Run...';
  
        try {
          const formData = new FormData(form);
          const response = await fetch(form.action, {
            method: 'POST',
            body: formData,
          });
          const data = await response.json();
  
          if (!response.ok) {
            throw new Error(data.error || 'Failed to create run');
          }
  
          if (data.run_name) {
            // Immediately redirect to the results page
            window.location.href = `/results/${data.run_name}`;
          } else {
            throw new Error('No run_name returned.');
          }
        } catch (error) {
          showToast('Error: ' + error.message, 'error');
          submitButton.disabled = false;
          if (submitSpinner) submitSpinner.classList.add('hidden');
          if (submitText) submitText.textContent = 'Generate Image';
        }
      });
    }
  
    // Deletion modal logic
    let runToDelete = null;
    const deleteModal = document.getElementById('deleteModal');
    if (deleteModal) {
      window.confirmDelete = (runName) => {
        runToDelete = runName;
        deleteModal.classList.remove('hidden');
      };
  
      window.hideDeleteModal = () => {
        runToDelete = null;
        deleteModal.classList.add('hidden');
      };
  
      window.deleteRun = async () => {
        if (!runToDelete) return;
        try {
          const response = await fetch(`/runs/${runToDelete}/delete`, {
            method: 'POST',
          });
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.error || 'Failed to delete run');
          }
          hideDeleteModal();
          showToast('Run deleted successfully', 'success');
          setTimeout(() => window.location.reload(), 800);
        } catch (error) {
          showToast(error.message, 'error');
          hideDeleteModal();
        }
      };
    }
  }
  
  //
  // 5. Results Page ("/results/<run_name>" => data-page="results"):
  //    - Polling for status
  //    - Lightbox logic
  //    - Show/hide progress
  //
  
  function initResultsPage() {
    const bodyEl = document.querySelector('body[data-page="results"]');
    if (!bodyEl) return;
  
    // We check for elements in results.html
    // - progressBar, statusIndicator, etc.
    const runName = bodyEl.getAttribute('data-runname');
    const maxIters = parseInt(bodyEl.getAttribute('data-maxiters') || '10', 10);
    let isPolling = false;
    let hasCompletedNotification = false;
  
    const statusIndicator = document.getElementById('statusIndicator');
    const progressBar = document.getElementById('progressBar');
  
    // Polling
    async function checkIfStartedAndBegin() {
      try {
        const statusResp = await fetch(`/results/${runName}/status`);
        const statusData = await statusResp.json();
  
        if (statusData.error) {
          showToast(statusData.error, 'error');
          return;
        }
  
        if (statusData.done) {
          updateProgressBar(statusData.images);
          updateStatusIndicator(true);
          return;
        }
  
        if (!statusData.started) {
          await fetch(`/start_run/${runName}`, { method: 'POST' });
        }
  
        if (!isPolling) {
          isPolling = true;
          pollUpdates();
        }
      } catch (err) {
        showToast('Failed to check run status. Please refresh the page.', 'error');
      }
    }
  
    async function pollUpdates() {
      if (!isPolling) return;
      try {
        const resp = await fetch(`/results/${runName}/status`);
        const data = await resp.json();
  
        if (data.error) {
          showToast(data.error, 'error');
          isPolling = false;
          return;
        }
  
        const { images, done, started } = data;
        if (!started) {
          setTimeout(pollUpdates, 3000);
          return;
        }
  
        updateProgressBar(images);
        updateStatusIndicator(done);
  
        if (done && !hasCompletedNotification) {
          hasCompletedNotification = true;
          showToast('Generation complete!', 'success');
          isPolling = false;
          return;
        }
  
        if (!done) {
          setTimeout(pollUpdates, 3000);
        }
      } catch (error) {
        setTimeout(pollUpdates, 5000);
      }
    }
  
    function updateProgressBar(images) {
      if (!progressBar) return;
      const currentCount = images.length;
      const percentage = (currentCount / maxIters) * 100;
      progressBar.style.width = `${percentage.toFixed(1)}%`;
      progressBar.style.transition = 'width 0.5s ease-in-out';
    }
  
    function updateStatusIndicator(done) {
      if (!statusIndicator) return;
      if (done) {
        statusIndicator.innerHTML = `
          <span class="inline-block h-3 w-3 rounded-full bg-green-500 mr-2"></span>
          <span class="text-sm text-gray-600 dark:text-gray-400">Complete</span>
        `;
      } else {
        statusIndicator.innerHTML = `
          <span class="animate-pulse inline-block h-3 w-3 rounded-full bg-blue-500 mr-2"></span>
          <span class="text-sm text-gray-600 dark:text-gray-400">Generating...</span>
        `;
      }
    }
  
    // Lightbox logic
    let currentImageIndex = 0;
    const imageData = [];
    const imageLightbox = document.getElementById('imageLightbox');
    const lightboxImage = document.getElementById('lightboxImage');
    const lightboxCaption = document.getElementById('lightboxCaption');
    const imageCounter = document.getElementById('imageCounter');
    const prevImageBtn = document.getElementById('prevImage');
    const nextImageBtn = document.getElementById('nextImage');
  
    // Show image in lightbox
    window.showImageLightbox = function (imageSrc, iteration) {
      if (!imageLightbox || !lightboxImage) return;
      // find or push to imageData if not present
      // For simplicity, we won't re-scan the entire DOM for images each time.
      // We'll just open the image directly:
      lightboxImage.src = imageSrc;
      if (lightboxCaption) lightboxCaption.textContent = `Iteration ${iteration}`;
      imageCounter.textContent = `1 / 1`; // minimal usage if not maintaining a full array
      imageLightbox.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
      // fade in
      lightboxImage.style.opacity = '0';
      lightboxImage.style.transform = 'scale(0.95)';
      lightboxImage.onload = () => {
        lightboxImage.style.opacity = '1';
        lightboxImage.style.transform = 'scale(1)';
      };
    };
  
    window.hideImageLightbox = function () {
      if (!imageLightbox || !lightboxImage) return;
      lightboxImage.style.opacity = '0';
      lightboxImage.style.transform = 'scale(0.95)';
      setTimeout(() => {
        imageLightbox.classList.add('hidden');
        document.body.style.overflow = '';
      }, 200);
    };
  
    if (prevImageBtn) prevImageBtn.classList.add('hidden');
    if (nextImageBtn) nextImageBtn.classList.add('hidden');
  
    // Start checks
    if (runName) {
      checkIfStartedAndBegin();
    }
  }
  
  //
  // 6. Gallery Page ("/gallery" => data-page="gallery"):
  //    - Just a simple image modal logic (some is already in results).
  //    - Basic search filter is inline but we can unify if needed.
  //
  function initGalleryPage() {
    // Fullscreen view logic
    window.viewFullImage = (url) => {
      const modal = document.getElementById('imageModal');
      const img = document.getElementById('modalImage');
      if (!modal || !img) return;
  
      img.src = url;
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    };
  
    window.closeImageModal = () => {
      const modal = document.getElementById('imageModal');
      if (!modal) return;
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    };
  
    // Download
    window.downloadImage = (url, filename) => {
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    };
  
    // Search / filter
    const searchBox = document.getElementById('searchBox');
    if (searchBox) {
      searchBox.addEventListener('input', function () {
        const searchTerm = this.value.toLowerCase();
        const imageCards = document.querySelectorAll('.image-card');
        imageCards.forEach((card) => {
          const goalText = card.getAttribute('data-goal') || '';
          if (goalText.includes(searchTerm)) {
            card.classList.remove('hidden');
          } else {
            card.classList.add('hidden');
          }
        });
      });
    }
  }
  
  //
  // 7. Models Page ("/models" => data-page="models"):
  //    - Toggling password visibility
  //    - Submitting form
  //
  function initModelsPage() {
    // Toggle password visibility
    window.togglePasswordVisibility = (button) => {
      const input = button.parentElement.querySelector('input');
      const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
      input.setAttribute('type', type);
  
      const svg = button.querySelector('svg');
      if (type === 'text') {
        svg.innerHTML = `
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M13.875 18.825A10.05 10.05 0 0112 19
               c-4.478 0-8.268-2.943-9.543-7
               a9.97 9.97 0 011.563-3.029m5.858.908
               a3 3 0 114.243 4.243M9.878 9.878
               l4.242 4.242M9.88 9.88
               l-3.29-3.29m7.532 7.532
               l3.29 3.29M3 3l3.59 3.59
               m0 0A9.953 9.953 0 0112 5
               c4.478 0 8.268 2.943
               9.543 7-1.274 4.057-5.064 7
               -9.543 7-4.477 0-8.268-2.943
               -9.543-7z" />
        `;
      } else {
        svg.innerHTML = `
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M15 12a3 3 0 11-6 0
               3 3 0 016 0z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M2.458 12C3.732 7.943 7.523 5
               12 5c4.478 0 8.268 2.943
               9.542 7-1.274 4.057-5.064 7
               -9.542 7-4.477 0-8.268-2.943
               -9.542-7z" />
        `;
      }
    };
  }
  
  //
  // 8. Settings Page ("/settings" => data-page="settings"):
  //    - Handle forms for general/advanced settings
  //    - Danger zone actions
  //
  
  function initSettingsPage() {
    const generalForm = document.getElementById('general-settings-form');
    const advancedForm = document.getElementById('advanced-settings-form');
  
    if (generalForm) {
      generalForm.addEventListener('submit', function (e) {
        e.preventDefault();
        saveSettings(this, '/settings/general');
      });
    }
    if (advancedForm) {
      advancedForm.addEventListener('submit', function (e) {
        e.preventDefault();
        saveSettings(this, '/settings/advanced');
      });
    }
  
    async function saveSettings(form, endpoint) {
      const formData = new FormData(form);
      const submitButton = form.querySelector('button[type="submit"]');
      if (!submitButton) return;
  
      // Disable submit button and show loading state
      submitButton.disabled = true;
      const originalText = submitButton.textContent;
      submitButton.innerHTML = `
          <div class="spinner inline-block mr-2"></div>
          Saving...
      `;
  
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          body: formData,
        });
        if (!response.ok) {
          throw new Error('Failed to save settings');
        }
        const data = await response.json();
        showToast(data.message || 'Settings saved successfully!', 'success');
      } catch (error) {
        showToast('Error: ' + error.message, 'error');
      } finally {
        submitButton.disabled = false;
        submitButton.textContent = originalText;
      }
    }
  
    // Danger zone
    window.confirmReset = () => {
      if (
        confirm(
          'Are you sure you want to reset all settings to their default values? This action cannot be undone.'
        )
      ) {
        resetSettings();
      }
    };
    async function resetSettings() {
      try {
        const response = await fetch('/settings/reset', {
          method: 'POST',
        });
        if (!response.ok) {
          throw new Error('Failed to reset settings');
        }
        const data = await response.json();
        showToast(data.message || 'Settings reset to defaults', 'success');
        setTimeout(() => window.location.reload(), 1500);
      } catch (error) {
        showToast('Error: ' + error.message, 'error');
      }
    }
  
    window.confirmClearCache = () => {
      if (
        confirm('Are you sure you want to clear all cached data? This action cannot be undone.')
      ) {
        clearCache();
      }
    };
    async function clearCache() {
      try {
        const response = await fetch('/settings/clear-cache', {
          method: 'POST',
        });
        if (!response.ok) {
          throw new Error('Failed to clear cache');
        }
        const data = await response.json();
        showToast(data.message || 'Cache cleared', 'success');
      } catch (error) {
        showToast('Error: ' + error.message, 'error');
      }
    }
  }
  
  //
  // 9. Workflows Page ("/workflows" => data-page="workflows"):
  //    - Upload new JSON workflow
  //    - Download or delete existing
  //
  
  function initWorkflowsPage() {
    // We'll attach the file input or drag/drop
    const uploadForm = document.getElementById('upload-form');
    const dropZone = document.getElementById('drop-zone');
  
    if (dropZone) {
      ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eName) => {
        dropZone.addEventListener(eName, preventDefaults, false);
      });
      function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
      }
      ['dragenter', 'dragover'].forEach((eName) => {
        dropZone.addEventListener(eName, () => highlight(true), false);
      });
      ['dragleave', 'drop'].forEach((eName) => {
        dropZone.addEventListener(eName, () => highlight(false), false);
      });
      function highlight(on) {
        if (on) {
          dropZone.classList.add(
            'border-blue-500',
            'bg-blue-50',
            'dark:bg-blue-900/20'
          );
        } else {
          dropZone.classList.remove(
            'border-blue-500',
            'bg-blue-50',
            'dark:bg-blue-900/20'
          );
        }
      }
      dropZone.addEventListener('drop', handleDrop, false);
      function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
      }
      function handleFiles(files) {
        if (files.length > 0) {
          const file = files[0];
          if (
            file.type === 'application/json' ||
            file.name.toLowerCase().endsWith('.json')
          ) {
            uploadWorkflow(file);
          } else {
            showToast('Please upload a JSON file', 'error');
          }
        }
      }
    }
  
    window.handleFileSelect = (input) => {
      const files = input.files;
      if (files.length > 0) {
        const file = files[0];
        if (
          file.type === 'application/json' ||
          file.name.toLowerCase().endsWith('.json')
        ) {
          uploadWorkflow(file);
        } else {
          showToast('Please upload a JSON file', 'error');
        }
      }
    };
  
    async function uploadWorkflow(file) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const response = await fetch('/workflows', {
          method: 'POST',
          body: formData,
        });
        if (!response.ok) throw new Error('Failed to upload workflow');
        showToast('Workflow uploaded successfully', 'success');
        setTimeout(() => window.location.reload(), 1000);
      } catch (err) {
        showToast('Error: ' + err.message, 'error');
      }
    }
  
    // Download
    window.downloadWorkflow = () => {
      const a = document.createElement('a');
      a.href = '/workflows/download';
      a.download = 'workflow.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    };
  
    // Delete
    window.deleteWorkflow = async () => {
      if (
        !confirm(
          'Are you sure you want to delete this workflow? This action cannot be undone.'
        )
      ) {
        return;
      }
      try {
        const response = await fetch('/workflows/delete', { method: 'POST' });
        if (!response.ok) throw new Error('Failed to delete workflow');
        showToast('Workflow deleted successfully', 'success');
        setTimeout(() => window.location.reload(), 1000);
      } catch (err) {
        showToast('Error: ' + err.message, 'error');
      }
    };
  }
  
  //
  // 10. On DOMContentLoaded, detect which page we're on via data-page, then init.
  //
  document.addEventListener('DOMContentLoaded', () => {
    // Basic usage: read data-page from <body>
    const page = document.body.getAttribute('data-page');
  
    switch (page) {
      case 'index':
        initIndexPage();
        break;
      case 'results':
        initResultsPage();
        break;
      case 'gallery':
        initGalleryPage();
        break;
      case 'models':
        initModelsPage();
        break;
      case 'settings':
        initSettingsPage();
        break;
      case 'workflows':
        initWorkflowsPage();
        break;
      default:
        // No specific init
        break;
    }
  });
  