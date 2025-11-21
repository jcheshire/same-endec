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
    // Initialize tabs only if they exist (index.html)
    if (document.querySelector('.tab-button')) {
        initializeTabs();
    }

    // Load event codes (needed on both index and reference pages)
    loadEventCodes();

    // Initialize forms only if they exist (index.html)
    if (document.getElementById('encode-form')) {
        initializeEncodingForm();
    }
    if (document.getElementById('raw-encode-form')) {
        initializeRawEncodingForm();
    }
    if (document.getElementById('decode-form')) {
        initializeDecodingForm();
    }
    if (document.getElementById('county-search')) {
        initializeLocationLookup();
    }

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

        // Populate event code dropdown (only on index.html)
        const select = document.getElementById('event-code');
        if (select) {
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
        }

        // Populate reference page (if element exists)
        const refContainer = document.getElementById('event-codes-list');
        if (refContainer) {
            populateEventCodesReference();
        }

    } catch (error) {
        showError('Failed to load event codes: ' + error.message);
    }
}

// Populate event codes reference grid
function populateEventCodesReference() {
    const container = document.getElementById('event-codes-list');
    container.innerHTML = '';

    // Sort event codes alphabetically by code
    const sortedEntries = Object.entries(eventCodes).sort((a, b) => a[0].localeCompare(b[0]));

    sortedEntries.forEach(([code, description]) => {
        const item = document.createElement('div');
        item.className = 'event-code-item';
        item.innerHTML = `<strong>${code}</strong>: ${description}`;
        container.appendChild(item);
    });
}

// Initialize encoding form
function initializeEncodingForm() {
    const form = document.getElementById('encode-form');
    form.addEventListener('submit', handleEncode);
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

        // First get the preview message string
        const previewResponse = await fetch(`${API_BASE}/encode/preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!previewResponse.ok) {
            const error = await previewResponse.json();
            throw new Error(error.detail || 'Failed to generate message');
        }

        const previewResult = await previewResponse.json();

        // Then encode the audio
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

        // Get header WAV file as blob
        const blob = await response.blob();
        currentAudioBlob = blob;

        // Extract filename from response header
        const filename = getFilenameFromResponse(response);

        // Display message preview
        const previewText = document.getElementById('preview-text');
        previewText.textContent = previewResult.message;

        // Display header audio player
        const headerAudio = document.getElementById('header-audio');
        const audioURL = URL.createObjectURL(blob);
        headerAudio.src = audioURL;

        const encodeOutput = document.getElementById('encode-output');
        encodeOutput.classList.remove('hidden');

        // Setup download button
        const downloadBtn = document.getElementById('download-header-btn');
        downloadBtn.onclick = () => downloadWAV(blob, filename);

        // Scroll to output
        encodeOutput.scrollIntoView({ behavior: 'smooth' });

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
            body: JSON.stringify({ same_string: message })
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

        // Get header WAV file as blob
        const blob = await response.blob();
        currentAudioBlob = blob;

        // Extract filename from response header
        const filename = getFilenameFromResponse(response);

        // Display header audio player
        const headerAudio = document.getElementById('header-audio');
        const audioURL = URL.createObjectURL(blob);
        headerAudio.src = audioURL;

        const encodeOutput = document.getElementById('encode-output');
        encodeOutput.classList.remove('hidden');

        // Setup download button
        const downloadBtn = document.getElementById('download-header-btn');
        downloadBtn.onclick = () => downloadWAV(blob, filename);

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

        // Format the decoded message nicely
        if (result.success && result.messages.length > 0) {
            let html = '';
            result.messages.forEach((msg, index) => {
                const p = msg.parsed;
                html += `<div class="decoded-message">`;

                // Show warning if message is partial
                if (p.partial) {
                    html += `<div class="decode-warning">`;
                    html += `<strong>⚠️ Partial Message Detected</strong>`;
                    html += `<p>This message may be incomplete due to audio quality or decoding issues. Some information may be missing.</p>`;
                    html += `</div>`;
                }

                // Event information
                html += `<div class="decode-section">`;
                html += `<h4>Event Type</h4>`;
                html += `<p class="decode-highlight">${escapeHtml(p.event_description || p.event || 'Unknown')}</p>`;
                if (p.event) {
                    html += `<p class="decode-detail">Code: ${escapeHtml(p.event)}</p>`;
                }
                html += `</div>`;

                // Originator
                html += `<div class="decode-section">`;
                html += `<h4>Issued By</h4>`;
                html += `<p>${escapeHtml(p.org_description || p.org || 'Unknown')}</p>`;
                if (p.org && p.org_description) {
                    html += `<p class="decode-detail">Originator: ${escapeHtml(p.org)}</p>`;
                }
                html += `</div>`;

                // Locations
                if (p.location_details && p.location_details.length > 0) {
                    html += `<div class="decode-section">`;
                    html += `<h4>Affected Areas</h4>`;
                    html += `<ul class="location-list">`;
                    p.location_details.forEach(loc => {
                        let locationText = '';
                        if (loc.subdivision) {
                            locationText = `${escapeHtml(loc.subdivision)} of ${escapeHtml(loc.name)}, ${escapeHtml(loc.state)}`;
                        } else {
                            locationText = `${escapeHtml(loc.name)}, ${escapeHtml(loc.state)}`;
                        }
                        html += `<li>${locationText} <span class="fips-code">(${escapeHtml(loc.fips)})</span></li>`;
                    });
                    html += `</ul>`;
                    html += `</div>`;
                }

                // Duration
                if (p.duration_readable) {
                    html += `<div class="decode-section">`;
                    html += `<h4>Duration</h4>`;
                    html += `<p>${escapeHtml(p.duration_readable)}</p>`;
                    html += `<p class="decode-detail">Code: ${escapeHtml(p.duration)}</p>`;
                    html += `</div>`;
                }

                // Timestamp
                if (p.timestamp_readable) {
                    html += `<div class="decode-section">`;
                    html += `<h4>Issued</h4>`;
                    html += `<p>${escapeHtml(p.timestamp_readable)}</p>`;
                    if (p.originator) {
                        html += `<p class="decode-detail">Callsign: ${escapeHtml(p.originator)}</p>`;
                    }
                    html += `</div>`;
                }

                // Raw message
                html += `<div class="decode-section">`;
                html += `<h4>Raw SAME Message</h4>`;
                html += `<code>${escapeHtml(msg.raw)}</code>`;
                html += `</div>`;

                html += `</div>`;
            });

            decodeText.innerHTML = html;
        } else {
            decodeText.textContent = JSON.stringify(result, null, 2);
        }

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
                searchResults.innerHTML = data.results.map((county, index) => {
                    const alreadySelected = selectedCounties.some(c => c.fips === county.fips);
                    return `
                        <div class="search-result-item ${alreadySelected ? 'disabled' : ''}"
                             data-fips="${county.fips}"
                             data-name="${county.name}"
                             data-state="${county.state}"
                             data-subdivision="${county.subdivision || ''}">
                            ${county.name}, ${county.state} <span class="fips-code">(${county.fips})</span>
                        </div>
                    `;
                }).join('');

                searchResults.classList.remove('hidden');

                // Add click handlers
                searchResults.querySelectorAll('.search-result-item:not(.disabled):not(.no-results)').forEach(item => {
                    item.addEventListener('click', () => {
                        const isNumericSearch = query.trim() && !isNaN(query.trim());

                        if (isNumericSearch) {
                            // Numeric search - add directly without subdivision selector
                            const countyData = {
                                fips: item.dataset.fips,
                                name: item.dataset.name,
                                state: item.dataset.state
                            };
                            // Add subdivision if present
                            if (item.dataset.subdivision && item.dataset.subdivision !== '') {
                                countyData.subdivision = item.dataset.subdivision;
                            }
                            addCounty(countyData);
                            searchInput.value = '';
                            searchResults.classList.add('hidden');
                        } else {
                            // Text search - show subdivision selector
                            searchResults.classList.add('hidden');
                            showSubdivisionSelector({
                                fips: item.dataset.fips,
                                name: item.dataset.name,
                                state: item.dataset.state
                            });
                        }
                    });
                });

            } catch (error) {
                searchResults.innerHTML = '<div class="search-result-item no-results">Search error</div>';
                searchResults.classList.remove('hidden');
            }
        }, 300);
    });

    // Close results when clicking outside
    const subdivisionContainer = document.getElementById('subdivision-selector-container');
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) &&
            !searchResults.contains(e.target) &&
            !subdivisionContainer.contains(e.target)) {
            searchResults.classList.add('hidden');
            subdivisionContainer.classList.add('hidden');
        }
    });

    // Show subdivision selector for a county
    function showSubdivisionSelector(county) {
        const selectorDiv = document.getElementById('subdivision-selector-container');

        // Build subdivision selector HTML
        const baseFips = county.fips.substring(1); // Remove leading 0 to get base 5-digit code
        const subdivisions = [
            { code: '1', name: 'NW', fullName: 'Northwest' },
            { code: '2', name: 'N', fullName: 'North' },
            { code: '3', name: 'NE', fullName: 'Northeast' },
            { code: '4', name: 'W', fullName: 'West' },
            { code: '5', name: 'C', fullName: 'Central' },
            { code: '6', name: 'E', fullName: 'East' },
            { code: '7', name: 'SW', fullName: 'Southwest' },
            { code: '8', name: 'S', fullName: 'South' },
            { code: '9', name: 'SE', fullName: 'Southeast' }
        ];

        selectorDiv.innerHTML = `
            <div class="subdivision-selector-header">${county.name}, ${county.state}</div>

            <div class="subdivision-options-container">
                <div class="whole-county-option">
                    <label class="subdivision-checkbox-wrapper">
                        <input type="checkbox" id="whole-county-checkbox">
                        <span class="subdivision-label">Whole County</span>
                    </label>
                </div>

                <div class="subdivision-grid">
                    ${subdivisions.map(sub => `
                        <label class="subdivision-checkbox-wrapper">
                            <input type="checkbox" value="${sub.code}" data-name="${sub.fullName}">
                            <span class="subdivision-label">${sub.name}</span>
                        </label>
                    `).join('')}
                </div>
            </div>

            <div class="subdivision-actions">
                <button type="button" class="btn btn-secondary cancel-btn">Cancel</button>
                <button type="button" class="btn btn-primary add-btn">Add Selected</button>
            </div>
        `;

        selectorDiv.classList.remove('hidden');

        // Handle whole county checkbox interaction
        const wholeCountyCheckbox = selectorDiv.querySelector('#whole-county-checkbox');
        const subdivisionGrid = selectorDiv.querySelector('.subdivision-grid');
        const subdivisionCheckboxes = selectorDiv.querySelectorAll('.subdivision-grid input[type="checkbox"]');

        wholeCountyCheckbox.addEventListener('change', () => {
            if (wholeCountyCheckbox.checked) {
                // Disable and uncheck all subdivisions
                subdivisionGrid.classList.add('disabled');
                subdivisionCheckboxes.forEach(cb => {
                    cb.checked = false;
                    cb.disabled = true;
                });
            } else {
                // Enable subdivisions
                subdivisionGrid.classList.remove('disabled');
                subdivisionCheckboxes.forEach(cb => cb.disabled = false);
            }
        });

        // Check if all subdivisions are selected -> suggest whole county
        subdivisionCheckboxes.forEach(cb => {
            cb.addEventListener('change', () => {
                const checkedCount = Array.from(subdivisionCheckboxes).filter(c => c.checked).length;
                if (checkedCount === 9) {
                    // All selected - suggest whole county
                    showToast('All subdivisions selected - consider using Whole County option');
                }

                // Uncheck whole county if any subdivision is selected
                if (cb.checked && wholeCountyCheckbox.checked) {
                    wholeCountyCheckbox.checked = false;
                    subdivisionGrid.classList.remove('disabled');
                    subdivisionCheckboxes.forEach(cb => cb.disabled = false);
                }
            });
        });

        // Cancel button
        selectorDiv.querySelector('.cancel-btn').addEventListener('click', () => {
            selectorDiv.classList.add('hidden');
        });

        // Add button
        selectorDiv.querySelector('.add-btn').addEventListener('click', () => {
            if (wholeCountyCheckbox.checked) {
                // Add whole county
                addCounty({
                    fips: '0' + baseFips,
                    name: county.name,
                    state: county.state
                });
            } else {
                // Add selected subdivisions
                const selected = Array.from(subdivisionCheckboxes).filter(cb => cb.checked);
                if (selected.length === 0) {
                    showToast('Please select at least one option');
                    return;
                }

                selected.forEach(cb => {
                    addCounty({
                        fips: cb.value + baseFips,
                        name: county.name,
                        state: county.state,
                        subdivision: cb.dataset.name
                    });
                });
            }

            selectorDiv.classList.add('hidden');
            searchInput.value = '';
            searchResults.classList.add('hidden');
        });
    }

    // Show toast notification
    function showToast(message) {
        // Simple toast - could be enhanced with better styling
        const toast = document.createElement('div');
        toast.textContent = message;
        toast.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #333; color: white; padding: 1rem; border-radius: 0.375rem; z-index: 1000; box-shadow: 0 4px 6px rgba(0,0,0,0.1);';
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }

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

        selectedCountiesDiv.innerHTML = selectedCounties.map(county => {
            const displayName = county.subdivision
                ? `${county.name}, ${county.state} - ${county.subdivision}`
                : `${county.name}, ${county.state}`;

            const tagClass = county.subdivision ? 'county-tag subdivision-tag' : 'county-tag';

            return `
                <span class="${tagClass}">
                    ${displayName} (${county.fips})
                    <button type="button" class="remove-county" data-fips="${county.fips}">&times;</button>
                </span>
            `;
        }).join('');

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

// HTML escape function to prevent XSS
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Extract filename from Content-Disposition header
function getFilenameFromResponse(response) {
    const disposition = response.headers.get('Content-Disposition');
    if (disposition) {
        const filenameMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
            return filenameMatch[1].replace(/['"]/g, '');
        }
    }
    return 'same_header.wav'; // Fallback
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
    if (!errorBox) return; // Element doesn't exist on this page

    const closeBtn = errorBox.querySelector('.error-close');

    closeBtn.addEventListener('click', () => {
        errorBox.classList.add('hidden');
    });
}

function showError(message) {
    const errorBox = document.getElementById('error-box');
    const errorMessage = document.getElementById('error-message');

    // If error box doesn't exist on this page, log to console instead
    if (!errorBox || !errorMessage) {
        console.error(message);
        return;
    }

    errorMessage.textContent = message;
    errorBox.classList.remove('hidden');

    // Auto-hide after 10 seconds
    setTimeout(() => {
        errorBox.classList.add('hidden');
    }, 10000);
}
