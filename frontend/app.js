// SAME Encoder/Decoder Frontend
// Pure vanilla JavaScript - no external dependencies

// Use relative URL for API calls - works with nginx reverse proxy
// When nginx is configured, all requests to /api/* are proxied to backend
const API_BASE = '/api';

// State
let eventCodes = {};
let currentAudioBlob = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeTabs();
    loadEventCodes();
    initializeEncodingForm();
    initializeRawEncodingForm();
    initializeDecodingForm();
    initializeLocationLookup();
    setupErrorHandler();
});

// Tab Navigation
function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');

            // Remove active class from all tabs
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Add active class to clicked tab
            button.classList.add('active');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        });
    });
}

// Load event codes from API
async function loadEventCodes() {
    try {
        const response = await fetch(`${API_BASE}/event-codes`);
        if (!response.ok) throw new Error('Failed to load event codes');

        eventCodes = await response.json();

        // Populate event code dropdown
        const select = document.getElementById('event-code');
        select.innerHTML = '<option value="">Select Event Code</option>';

        // Sort by code alphabetically
        Object.entries(eventCodes)
            .sort(([codeA], [codeB]) => codeA.localeCompare(codeB))
            .forEach(([code, description]) => {
                const option = document.createElement('option');
                option.value = code;
                option.textContent = `${code} - ${description}`;
                select.appendChild(option);
            });

        // Update description on change
        select.addEventListener('change', (e) => {
            const desc = document.getElementById('event-description');
            desc.textContent = eventCodes[e.target.value] || '';
        });

        // Populate reference tab
        populateEventCodesReference();

    } catch (error) {
        showError('Failed to load event codes: ' + error.message);
    }
}

// Populate event codes reference grid
function populateEventCodesReference() {
    const container = document.getElementById('event-codes-list');
    container.innerHTML = '';

    Object.entries(eventCodes).forEach(([code, description]) => {
        const item = document.createElement('div');
        item.className = 'event-code-item';
        item.innerHTML = `<strong>${code}</strong>: ${description}`;
        container.appendChild(item);
    });
}

// Initialize encoding form
function initializeEncodingForm() {
    const form = document.getElementById('encode-form');
    const previewBtn = document.getElementById('preview-btn');

    previewBtn.addEventListener('click', handlePreview);
    form.addEventListener('submit', handleEncode);
}

// Handle preview
async function handlePreview(e) {
    e.preventDefault();

    // Validate event code
    const eventCode = document.getElementById('event-code').value;
    if (!eventCode || eventCode.trim() === '') {
        showError('Please select an event code from the dropdown');
        return;
    }

    // Validate location codes
    const locationCodesValue = document.getElementById('location-codes').value;
    if (!locationCodesValue || locationCodesValue.trim() === '') {
        showError('Please select at least one county');
        return;
    }

    const data = {
        event_code: eventCode,
        originator: document.getElementById('originator').value,
        location_codes: locationCodesValue.split(',').map(s => s.trim()).filter(s => s.length > 0),
        duration: document.getElementById('duration').value,
        callsign: document.getElementById('callsign').value || undefined
    };

    try {
        showLoading(true);
        const response = await fetch(`${API_BASE}/encode/preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const error = await response.json();
            // Handle Pydantic validation errors (422)
            if (response.status === 422 && error.detail) {
                if (Array.isArray(error.detail)) {
                    // Format validation errors nicely
                    const messages = error.detail.map(e => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join(', ');
                    throw new Error(messages);
                } else if (typeof error.detail === 'string') {
                    throw new Error(error.detail);
                }
            }
            throw new Error(error.detail || 'Preview failed');
        }

        const result = await response.json();

        const previewOutput = document.getElementById('preview-output');
        const previewText = document.getElementById('preview-text');

        previewText.textContent = result.message;
        previewOutput.classList.remove('hidden');

    } catch (error) {
        // Handle different error types
        let errorMsg = 'Preview failed';
        if (error.message && typeof error.message === 'string') {
            errorMsg += ': ' + error.message;
        } else if (error.detail) {
            errorMsg += ': ' + error.detail;
        }
        showError(errorMsg);
    } finally {
        showLoading(false);
    }
}

// Handle encoding
async function handleEncode(e) {
    e.preventDefault();

    // Validate event code
    const eventCode = document.getElementById('event-code').value;
    if (!eventCode || eventCode.trim() === '') {
        showError('Please select an event code from the dropdown');
        return;
    }

    // Validate location codes
    const locationCodesValue = document.getElementById('location-codes').value;
    if (!locationCodesValue || locationCodesValue.trim() === '') {
        showError('Please select at least one county');
        return;
    }

    const data = {
        event_code: eventCode,
        originator: document.getElementById('originator').value,
        location_codes: locationCodesValue.split(',').map(s => s.trim()).filter(s => s.length > 0),
        duration: document.getElementById('duration').value,
        callsign: document.getElementById('callsign').value || undefined
    };

    try {
        showLoading(true);
        const response = await fetch(`${API_BASE}/encode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const error = await response.json();
            // Handle Pydantic validation errors (422)
            if (response.status === 422 && error.detail) {
                if (Array.isArray(error.detail)) {
                    // Format validation errors nicely
                    const messages = error.detail.map(e => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join(', ');
                    throw new Error(messages);
                } else if (typeof error.detail === 'string') {
                    throw new Error(error.detail);
                }
            }
            throw new Error(error.detail || 'Encoding failed');
        }

        // Get WAV file as blob
        const blob = await response.blob();
        currentAudioBlob = blob;

        // Display audio player
        const audioPlayer = document.getElementById('audio-player');
        const audioURL = URL.createObjectURL(blob);
        audioPlayer.src = audioURL;

        const encodeOutput = document.getElementById('encode-output');
        encodeOutput.classList.remove('hidden');

        // Setup download button
        const downloadBtn = document.getElementById('download-btn');
        downloadBtn.onclick = () => downloadWAV(blob, 'same_message.wav');

    } catch (error) {
        showError('Encoding failed: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// Initialize raw encoding form
function initializeRawEncodingForm() {
    const form = document.getElementById('raw-encode-form');
    form.addEventListener('submit', handleRawEncode);
}

// Handle raw encoding
async function handleRawEncode(e) {
    e.preventDefault();

    const message = document.getElementById('raw-message').value;

    try {
        showLoading(true);
        const response = await fetch(`${API_BASE}/encode/raw`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        if (!response.ok) {
            const error = await response.json();
            // Handle Pydantic validation errors (422)
            if (response.status === 422 && error.detail) {
                if (Array.isArray(error.detail)) {
                    // Format validation errors nicely
                    const messages = error.detail.map(e => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join(', ');
                    throw new Error(messages);
                } else if (typeof error.detail === 'string') {
                    throw new Error(error.detail);
                }
            }
            throw new Error(error.detail || 'Encoding failed');
        }

        // Get WAV file as blob
        const blob = await response.blob();
        currentAudioBlob = blob;

        // Display audio player
        const audioPlayer = document.getElementById('audio-player');
        const audioURL = URL.createObjectURL(blob);
        audioPlayer.src = audioURL;

        const encodeOutput = document.getElementById('encode-output');
        encodeOutput.classList.remove('hidden');

        // Setup download button
        const downloadBtn = document.getElementById('download-btn');
        downloadBtn.onclick = () => downloadWAV(blob, 'same_message.wav');

        // Scroll to output
        encodeOutput.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        showError('Encoding failed: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// Initialize decoding form
function initializeDecodingForm() {
    const form = document.getElementById('decode-form');
    form.addEventListener('submit', handleDecode);
}

// Handle decoding
async function handleDecode(e) {
    e.preventDefault();

    const fileInput = document.getElementById('wav-file');
    const file = fileInput.files[0];

    if (!file) {
        showError('Please select a WAV file');
        return;
    }

    // Check file size (10MB limit)
    if (file.size > 10 * 1024 * 1024) {
        showError('File size exceeds 10MB limit');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        showLoading(true);
        const response = await fetch(`${API_BASE}/decode`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Decoding failed');
        }

        const result = await response.json();

        const decodeOutput = document.getElementById('decode-output');
        const decodeText = document.getElementById('decode-text');

        decodeText.textContent = JSON.stringify(result, null, 2);
        decodeOutput.classList.remove('hidden');

        // Scroll to output
        decodeOutput.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        showError('Decoding failed: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// County search with autocomplete
function initializeLocationLookup() {
    const searchInput = document.getElementById('county-search');
    const searchResults = document.getElementById('search-results');
    const selectedCountiesDiv = document.getElementById('selected-counties');
    const hiddenInput = document.getElementById('location-codes');

    let selectedCounties = [];
    let debounceTimer;

    // Search as user types
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const query = searchInput.value.trim();

        if (query.length < 2) {
            searchResults.classList.add('hidden');
            return;
        }

        debounceTimer = setTimeout(async () => {
            try {
                const response = await fetch(`${API_BASE}/fips-search?q=${encodeURIComponent(query)}&limit=20`);
                if (!response.ok) throw new Error('Search failed');

                const data = await response.json();

                if (data.results.length === 0) {
                    searchResults.innerHTML = '<div class="search-result-item no-results">No counties found</div>';
                    searchResults.classList.remove('hidden');
                    return;
                }

                // Display results
                searchResults.innerHTML = data.results.map(county => {
                    const alreadySelected = selectedCounties.some(c => c.fips === county.fips);
                    return `
                        <div class="search-result-item ${alreadySelected ? 'disabled' : ''}" data-fips="${county.fips}" data-name="${county.name}" data-state="${county.state}">
                            ${county.name}, ${county.state} <span class="fips-code">(${county.fips})</span>
                        </div>
                    `;
                }).join('');

                searchResults.classList.remove('hidden');

                // Add click handlers
                searchResults.querySelectorAll('.search-result-item:not(.disabled):not(.no-results)').forEach(item => {
                    item.addEventListener('click', () => {
                        addCounty({
                            fips: item.dataset.fips,
                            name: item.dataset.name,
                            state: item.dataset.state
                        });
                        searchInput.value = '';
                        searchResults.classList.add('hidden');
                    });
                });

            } catch (error) {
                searchResults.innerHTML = '<div class="search-result-item no-results">Search error</div>';
                searchResults.classList.remove('hidden');
            }
        }, 300);
    });

    // Close results when clicking outside
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.classList.add('hidden');
        }
    });

    // Add county to selection
    function addCounty(county) {
        // Check if already added
        if (selectedCounties.some(c => c.fips === county.fips)) {
            return;
        }

        selectedCounties.push(county);
        updateSelectedCountiesDisplay();
        updateHiddenInput();
    }

    // Remove county from selection
    function removeCounty(fips) {
        selectedCounties = selectedCounties.filter(c => c.fips !== fips);
        updateSelectedCountiesDisplay();
        updateHiddenInput();
    }

    // Update the visual display of selected counties
    function updateSelectedCountiesDisplay() {
        if (selectedCounties.length === 0) {
            selectedCountiesDiv.innerHTML = '<span class="help-text">No counties selected. Search and click to add.</span>';
            return;
        }

        selectedCountiesDiv.innerHTML = selectedCounties.map(county => `
            <span class="county-tag">
                ${county.name}, ${county.state} (${county.fips})
                <button type="button" class="remove-county" data-fips="${county.fips}">&times;</button>
            </span>
        `).join('');

        // Add remove handlers
        selectedCountiesDiv.querySelectorAll('.remove-county').forEach(btn => {
            btn.addEventListener('click', () => {
                removeCounty(btn.dataset.fips);
            });
        });
    }

    // Update hidden input with comma-separated FIPS codes
    function updateHiddenInput() {
        // Pad FIPS codes to 6 digits (SAME protocol requires PSSCCC format)
        hiddenInput.value = selectedCounties.map(c => c.fips.padStart(6, '0')).join(',');
    }
}

// Download WAV file
function downloadWAV(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Show/hide loading spinner
function showLoading(show) {
    const loading = document.getElementById('loading');
    if (show) {
        loading.classList.remove('hidden');
    } else {
        loading.classList.add('hidden');
    }
}

// Error handling
function setupErrorHandler() {
    const errorBox = document.getElementById('error-box');
    const closeBtn = errorBox.querySelector('.error-close');

    closeBtn.addEventListener('click', () => {
        errorBox.classList.add('hidden');
    });
}

function showError(message) {
    const errorBox = document.getElementById('error-box');
    const errorMessage = document.getElementById('error-message');

    errorMessage.textContent = message;
    errorBox.classList.remove('hidden');

    // Auto-hide after 10 seconds
    setTimeout(() => {
        errorBox.classList.add('hidden');
    }, 10000);
}
