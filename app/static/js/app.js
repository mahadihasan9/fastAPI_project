// Toast utility
function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    if (!toast) return;
    toast.innerHTML = (type === "success" ? "✅ " : "⚠️ ") + message;
    toast.style.borderColor = type === "success" ? "rgba(16, 185, 129, 0.4)" : "rgba(239, 68, 68, 0.4)";
    toast.classList.add("show");
    setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}

// Copy to Clipboard
function copyToClipboard(text, alertMessage) {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(alertMessage || "Copied to clipboard!");
        }).catch(err => {
            fallbackCopy(text, alertMessage);
        });
    } else {
        fallbackCopy(text, alertMessage);
    }
}

function fallbackCopy(text, alertMessage) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.setAttribute("readonly", "");
    textArea.style.position = "fixed";
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.width = "2em";
    textArea.style.height = "2em";
    textArea.style.padding = "0";
    textArea.style.border = "none";
    textArea.style.outline = "none";
    textArea.style.boxShadow = "none";
    textArea.style.background = "transparent";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    textArea.setSelectionRange(0, 99999);
    try {
        const success = document.execCommand('copy');
        if (success) {
            showToast(alertMessage || "Copied to clipboard!");
        } else {
            showToast("Failed to copy", "error");
        }
    } catch (err) {
        showToast("Failed to copy", "error");
    }
    document.body.removeChild(textArea);
}

// Target Size Slider live sync
document.addEventListener("DOMContentLoaded", () => {
    const slider = document.getElementById("targetSizeSlider");
    const badge = document.getElementById("targetSizeVal");

    if (slider && badge) {
        slider.addEventListener("input", (e) => {
            badge.innerText = `${e.target.value} KB`;
        });
    }

    // File input & Drag/Drop
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("fileInput");
    const previewContainer = document.getElementById("previewContainer");
    const previewImg = document.getElementById("previewImg");
    const previewName = document.getElementById("previewName");
    const previewSize = document.getElementById("previewSize");
    const uploadForm = document.getElementById("uploadForm");
    const uploadBtn = document.getElementById("uploadBtn");

    if (dropzone && fileInput) {
        dropzone.addEventListener("click", () => fileInput.click());

        dropzone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropzone.classList.add("dragover");
        });

        dropzone.addEventListener("dragleave", () => {
            dropzone.classList.remove("dragover");
        });

        dropzone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropzone.classList.remove("dragover");
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener("change", (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
            }
        });
    }

    function handleFileSelect(file) {
        if (!file.type.startsWith("image/")) {
            showToast("Please select a valid image file", "error");
            return;
        }

        previewName.innerText = file.name;
        const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
        const sizeKb = (file.size / 1024).toFixed(1);
        previewSize.innerText = file.size > 1024 * 1024 ? `Original: ${sizeMb} MB` : `Original: ${sizeKb} KB`;

        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
            previewContainer.style.display = "flex";
        };
        reader.readAsDataURL(file);
    }

    // Upload form submit
    if (uploadForm) {
        uploadForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            if (!fileInput.files || fileInput.files.length === 0) {
                showToast("Please choose an image to upload", "error");
                return;
            }

            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            formData.append("target_size_kb", slider ? slider.value : 50);

            uploadBtn.disabled = true;
            uploadBtn.innerHTML = `<span>⏳ Compressing & Uploading...</span>`;

            try {
                const response = await fetch("/api/admin/upload", {
                    method: "POST",
                    body: formData
                });

                const data = await response.json();

                if (response.ok && data.status) {
                    showToast(`Photo saved! Compressed to ${data.photo.file_size_kb} KB`);
                    setTimeout(() => {
                        window.location.reload();
                    }, 1200);
                } else {
                    showToast(data.detail || data.error || "Upload failed", "error");
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = `<span>🚀 Upload & Compress Photo</span>`;
                }
            } catch (err) {
                showToast("Server error during upload", "error");
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = `<span>🚀 Upload & Compress Photo</span>`;
            }
        });
    }
});

// Delete Photo
async function deletePhoto(photoId) {
    if (!confirm("Are you sure you want to delete this photo?")) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/photo/${photoId}`, {
            method: "DELETE"
        });

        const data = await response.json();

        if (response.ok && data.status) {
            showToast("Photo deleted successfully!");
            const row = document.getElementById(`photo-row-${photoId}`);
            if (row) row.remove();
            const card = document.getElementById(`card-photo-${photoId}`);
            if (card) card.remove();
        } else {
            showToast(data.detail || data.error || "Failed to delete photo", "error");
        }
    } catch (err) {
        showToast("Error deleting photo", "error");
    }
}

// Unblock IP
async function unblockIpAddress(ip) {
    if (!confirm(`Are you sure you want to unblock IP: ${ip}?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/unblock-ip/${encodeURIComponent(ip)}`, {
            method: "POST"
        });

        const data = await response.json();

        if (response.ok && data.status) {
            showToast(`IP ${ip} unblocked!`);
            const row = document.getElementById(`ip-row-${ip.replace(/[^a-zA-Z0-9]/g, '_')}`);
            if (row) row.remove();
        } else {
            showToast(data.detail || data.error || "Failed to unblock IP", "error");
        }
    } catch (err) {
        showToast("Error unblocking IP", "error");
    }
}

// ==========================================
// Gallery View Switching & Lightbox
// ==========================================

function switchView(viewType) {
    const galleryView = document.getElementById("galleryView");
    const tableView = document.getElementById("tableView");
    const btnGallery = document.getElementById("btnGalleryView");
    const btnTable = document.getElementById("btnTableView");

    if (viewType === "table") {
        if (galleryView) galleryView.style.display = "none";
        if (tableView) tableView.style.display = "block";
        if (btnTable) btnTable.classList.add("active");
        if (btnGallery) btnGallery.classList.remove("active");
        localStorage.setItem("photo_view_mode", "table");
    } else {
        if (galleryView) galleryView.style.display = "grid";
        if (tableView) tableView.style.display = "none";
        if (btnGallery) btnGallery.classList.add("active");
        if (btnTable) btnTable.classList.remove("active");
        localStorage.setItem("photo_view_mode", "gallery");
    }
}

// Initialize saved view preference
document.addEventListener("DOMContentLoaded", () => {
    const savedMode = localStorage.getItem("photo_view_mode") || "gallery";
    switchView(savedMode);
});

// Lightbox Open / Close
function openLightbox(imgSrc, title, photoId, sizeKb, downloadUrl) {
    const modal = document.getElementById("lightboxModal");
    const img = document.getElementById("lightboxImg");
    const titleEl = document.getElementById("lightboxTitle");
    const sizeEl = document.getElementById("lightboxSize");
    const downloadBtn = document.getElementById("lightboxDownload");
    const copyBtn = document.getElementById("lightboxCopy");

    if (!modal || !img) return;

    img.src = imgSrc;
    if (titleEl) titleEl.innerText = title;
    if (sizeEl) sizeEl.innerText = `${sizeKb} KB`;
    if (downloadBtn) downloadBtn.href = downloadUrl;
    if (copyBtn) {
        copyBtn.onclick = () => copyToClipboard(imgSrc, "Photo URL copied!");
    }

    modal.classList.add("active");
}

function closeLightbox() {
    const modal = document.getElementById("lightboxModal");
    if (modal) modal.classList.remove("active");
}

// Close on Escape or click outside
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeLightbox();
});

