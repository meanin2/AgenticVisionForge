// static/scripts.js

// You can add JavaScript for interactivity here if desired. 

// Dark mode handling
document.addEventListener('alpine:init', () => {
    Alpine.store('darkMode', {
        on: false,
        toggle() {
            this.on = !this.on;
            document.documentElement.classList.toggle('dark', this.on);
            localStorage.setItem('darkMode', this.on);
        },
        init() {
            this.on = localStorage.getItem('darkMode') === 'true';
            document.documentElement.classList.toggle('dark', this.on);
        }
    });
});

// Toast notifications
function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast fixed bottom-5 right-5 p-4 rounded-lg shadow-lg text-white ${
        type === 'error' ? 'bg-red-500' :
        type === 'success' ? 'bg-green-500' :
        'bg-blue-500'
    }`;
    toast.textContent = message;
    
    document.getElementById('toast-container').appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, duration);
}

// Image gallery enhancements
function initializeGallery() {
    const images = document.querySelectorAll('.gallery-image img');
    images.forEach(img => {
        img.addEventListener('click', () => {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50';
            modal.innerHTML = `
                <div class="relative max-w-4xl mx-auto">
                    <img src="${img.src}" class="max-h-[90vh] max-w-[90vw] object-contain" />
                    <button class="absolute top-4 right-4 text-white text-2xl">&times;</button>
                </div>
            `;
            
            modal.addEventListener('click', (e) => {
                if (e.target === modal || e.target.tagName === 'BUTTON') {
                    modal.remove();
                }
            });
            
            document.body.appendChild(modal);
        });
    });
}

// Form validation and submission
function initializeForm() {
    const form = document.querySelector('form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const submitButton = form.querySelector('button[type="submit"]');
        const originalText = submitButton.textContent;
        
        // Show loading state
        submitButton.disabled = true;
        submitButton.innerHTML = `
            <div class="spinner inline-block mr-2"></div>
            Processing...
        `;
        
        try {
            const formData = new FormData(form);
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Submission failed');
            }
            
            const result = await response.json();
            showToast('Generation started successfully!', 'success');
            
            // Redirect to results page
            window.location.href = result.redirect;
            
        } catch (error) {
            showToast('Error: ' + error.message, 'error');
            submitButton.disabled = false;
            submitButton.textContent = originalText;
        }
    });
}

// Progress bar updates
function initializeProgress() {
    const progressBar = document.querySelector('.progress-bar');
    if (!progressBar) return;

    let progress = 0;
    const interval = setInterval(() => {
        progress += 1;
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
        
        if (progress >= 100) {
            clearInterval(interval);
        }
    }, 1000);
}

// Initialize all components
document.addEventListener('DOMContentLoaded', () => {
    initializeGallery();
    initializeForm();
    initializeProgress();
    initializeDragDrop();
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Toggle sidebar with Ctrl + B
    if (e.ctrlKey && e.key === 'b') {
        Alpine.store('sidebarOpen').toggle();
    }
    
    // Toggle dark mode with Ctrl + D
    if (e.ctrlKey && e.key === 'd') {
        Alpine.store('darkMode').toggle();
    }
});

// File upload preview
function handleFileUpload(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            const preview = document.getElementById('file-preview');
            if (preview) {
                preview.src = e.target.result;
                preview.classList.remove('hidden');
            }
        };
        
        reader.readAsDataURL(input.files[0]);
    }
}

// Drag and drop file handling
function initializeDragDrop() {
    const dropZone = document.querySelector('.drop-zone');
    if (!dropZone) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        dropZone.classList.add('border-blue-500');
    }

    function unhighlight(e) {
        dropZone.classList.remove('border-blue-500');
    }

    dropZone.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        ([...files]).forEach(uploadFile);
    }

    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
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
}

// DELETE image from gallery placeholder fix:
async function deleteGalleryImage(imageId) {
    try {
        const resp = await fetch(`/api/images/${imageId}`, {
            method: 'DELETE'
        });
        const data = await resp.json();
        if (!resp.ok) {
            throw new Error(data.error || 'Failed to delete image');
        }
        showToast(data.message || 'Image deleted', 'success');
        // Optionally refresh or remove the image from DOM
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}
