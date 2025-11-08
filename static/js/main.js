// Quality Alerts Dashboard JavaScript
console.log('[Quality Alerts] Script loaded!');

// Global chart instances
let mortalityChart = null;
let pbdChart = null;
let currentModelResults = null;  // Store current model results for CSV download
let currentModelId = null;  // Store current model ID

// Format date from YYYY-MM-DD to "Month YYYY" format
function formatDateLabel(dateString) {
    const date = new Date(dateString + 'T00:00:00'); // Add time to avoid timezone issues
    const months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    const month = months[date.getMonth()];
    const year = date.getFullYear();
    return `${month} ${year}`;
}

// Wait for Chart.js to be available
function waitForChart(callback, maxAttempts = 50) {
    if (typeof Chart !== 'undefined') {
        console.log('[Quality Alerts] Chart.js is available');
        callback();
    } else if (maxAttempts > 0) {
        console.log('[Quality Alerts] Waiting for Chart.js... (' + maxAttempts + ' attempts remaining)');
        setTimeout(() => waitForChart(callback, maxAttempts - 1), 100);
    } else {
        console.error('[Quality Alerts] Chart.js did not load after waiting. Some features may not work.');
        // Still initialize, but charts will fail gracefully
        callback();
    }
}

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('[Quality Alerts] DOM loaded, waiting for Chart.js...');
    waitForChart(function() {
        console.log('[Quality Alerts] Initializing dashboard...');
        loadHospitals();
        setDefaultDates();
        initTabs();
        
        document.getElementById('update-btn').addEventListener('click', updateChart);
    
    // Auto-update when hospital changes - but not on initial load
    // Only trigger when user manually changes after page load
    let initialLoad = true;
    document.getElementById('hospital-select').addEventListener('change', function() {
        if (!initialLoad) {
            updateChart();
        }
        initialLoad = false;
    });

    // Model selection change handler
    document.getElementById('model-select').addEventListener('change', function() {
        const model = this.value;
        if (model) {
            loadModelResults(model);
        } else {
            document.getElementById('models-results-container').style.display = 'none';
        }
    });
    
    console.log('[Quality Alerts] Event listeners attached');
    }); // End waitForChart callback
}); // End DOMContentLoaded

// Tab switching functionality
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');
            
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => {
                content.classList.remove('active');
                content.style.display = 'none';
            });
            
            // Add active class to clicked button and corresponding content
            this.classList.add('active');
            const targetContent = document.getElementById(targetTab + '-tab');
            if (targetContent) {
                targetContent.classList.add('active');
                targetContent.style.display = 'block';
            }
        });
    });
}

// Load list of hospitals
async function loadHospitals() {
    console.log('[Quality Alerts] Loading hospitals...');
    try {
        console.log('[Quality Alerts] Fetching /api/hospitals');
        const response = await fetch('/api/hospitals');
        console.log('[Quality Alerts] Response status:', response.status);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const hospitals = await response.json();
        console.log('[Quality Alerts] Received', hospitals.length, 'hospitals');
        
        const select = document.getElementById('hospital-select');
        select.innerHTML = '<option value="">Select a hospital...</option>';
        
        hospitals.forEach(hospital => {
            const option = document.createElement('option');
            option.value = hospital;
            option.textContent = hospital;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading hospitals:', error);
        document.getElementById('hospital-select').innerHTML = 
            '<option value="">Error loading hospitals</option>';
    }
}

// Set default date range (last 12 months)
function setDefaultDates() {
    const today = new Date();
    const endDate = today.toISOString().split('T')[0];
    
    const startDate = new Date(today);
    startDate.setMonth(startDate.getMonth() - 12);
    const startDateStr = startDate.toISOString().split('T')[0];
    
    document.getElementById('start-date').value = startDateStr;
    document.getElementById('end-date').value = endDate;
}

// Add timeout to fetch requests
const fetchWithTimeout = (url, options = {}, timeout = 30000) => {
    return Promise.race([
        fetch(url, options),
        new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Request timeout')), timeout)
        )
    ]);
};

// Update the chart with selected parameters
async function updateChart() {
    const hospital = document.getElementById('hospital-select').value;
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;
    
    if (!hospital) {
        alert('Please select a hospital');
        return;
    }
    
    if (!startDate || !endDate) {
        alert('Please select start and end dates');
        return;
    }
    
    // Show loading state
    const updateBtn = document.getElementById('update-btn');
    const originalText = updateBtn.textContent;
    updateBtn.disabled = true;
    updateBtn.textContent = 'Loading...';
    
    try {
        // Load mortality data first (fast, from database) with timeout
        // Backend timeout is max 120 seconds (query_current_month_mortality_all_hospitals)
        // Frontend timeout should be 5 seconds more = 125 seconds
        const response = await fetchWithTimeout(
            `/api/mortality-data?hospital_name=${encodeURIComponent(hospital)}&start_date=${startDate}&end_date=${endDate}`,
            {},
            125000  // 125 second timeout (120s backend max + 5s buffer)
        );
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        displayChart(data);
        updateStatistics(data.statistics);
        
        // Re-enable button immediately after main data loads
        updateBtn.disabled = false;
        updateBtn.textContent = originalText;
        
        // Load raw data (fast, from database) - non-blocking
        loadRawData(hospital, startDate, endDate).catch(err => {
            console.error('Error loading raw data:', err);
        });
        
        // Load PBD data in background (slow, from BigQuery) - completely non-blocking
        loadPBDData(hospital, startDate, endDate).catch(err => {
            console.error('Error loading PBD data:', err);
        });
        
    } catch (error) {
        console.error('Error fetching data:', error);
        alert('Error loading data: ' + error.message);
        updateBtn.disabled = false;
        updateBtn.textContent = originalText;
    }
}

// Display the chart
function displayChart(data) {
    const renderingContext = document.getElementById('mortality-chart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (mortalityChart) {
        mortalityChart.destroy();
    }
    
    // Prepare data
    const labels = data.monthly_data.map(d => formatDateLabel(d.date));
    const mortalityRates = data.monthly_data.map(d => d.mortality_rate);
    
    const avgRate = data.statistics ? data.statistics.avg_mortality_rate : null;
    const threshold = data.statistics ? data.statistics.threshold_3sd : null;
    
    // Create datasets
    const datasets = [
        {
            label: 'Mortality Rate (%)',
            data: mortalityRates,
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            tension: 0.1,
            fill: true
        }
    ];
    
    // Add average line
    if (avgRate !== null) {
        datasets.push({
            label: 'Average',
            data: Array(mortalityRates.length).fill(avgRate),
            borderColor: 'rgb(54, 162, 235)',
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false
        });
    }
    
    // Add +3SD threshold line
    if (threshold !== null) {
        datasets.push({
            label: 'Alert Threshold (+3SD)',
            data: Array(mortalityRates.length).fill(threshold),
            borderColor: 'rgb(255, 99, 132)',
            borderDash: [10, 5],
            pointRadius: 0,
            fill: false,
            borderWidth: 2
        });
    }
    
    // Check if Chart.js is loaded
    if (typeof Chart === 'undefined') {
        console.error('[Quality Alerts] Chart.js is not loaded! Please check if the CDN is accessible.');
        alert('Chart.js library failed to load. Please refresh the page or check your internet connection.');
        return;
    }
    
    // Create chart
    mortalityChart = new Chart(renderingContext, {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Mortality Rate Over Time',
                    font: {
                        size: 18
                    }
                },
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Mortality Rate (%)'
                    },
                    beginAtZero: true
                }
            }
        }
    });
    
    // Check for alerts
    checkAlerts(data);
}

// Update statistics display
function updateStatistics(statistics) {
    if (!statistics) {
        document.getElementById('avg-mortality').textContent = '-';
        document.getElementById('std-dev').textContent = '-';
        document.getElementById('threshold').textContent = '-';
        return;
    }
    
    document.getElementById('avg-mortality').textContent = 
        statistics.avg_mortality_rate.toFixed(2) + '%';
    document.getElementById('std-dev').textContent = 
        statistics.std_deviation.toFixed(2) + '%';
    document.getElementById('threshold').textContent = 
        statistics.threshold_3sd.toFixed(2) + '%';
}

// Check for alerts (mortality rate exceeding threshold)
function checkAlerts(data) {
    const alertsContainer = document.getElementById('alerts-container');
    const alertsList = document.getElementById('alerts-list');
    
    if (!data.statistics || !data.monthly_data || data.monthly_data.length === 0) {
        alertsContainer.style.display = 'none';
        return;
    }
    
    const threshold = data.statistics.threshold_3sd;
    const alerts = [];
    
    data.monthly_data.forEach(month => {
        if (month.mortality_rate > threshold) {
            alerts.push({
                date: month.date,
                rate: month.mortality_rate,
                threshold: threshold
            });
        }
    });
    
    if (alerts.length > 0) {
        alertsList.innerHTML = '';
        alerts.forEach(alert => {
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert-item';
            alertDiv.innerHTML = `
                <strong>Alert:</strong> Mortality rate ${alert.rate.toFixed(2)}% 
                exceeds threshold ${alert.threshold.toFixed(2)}% on ${alert.date}
            `;
            alertsList.appendChild(alertDiv);
        });
        alertsContainer.style.display = 'block';
    } else {
        alertsContainer.style.display = 'none';
    }
}

// Load and display PBD data
async function loadPBDData(hospital, startDate, endDate) {
    console.log('[Quality Alerts] Loading PBD data...');
    
    // Show loading indicator
    const pbdCanvas = document.getElementById('pbd-chart');
    if (pbdCanvas && pbdChart) {
        pbdChart.destroy();
        pbdChart = null;
    }
    
    const pbdContainer = document.querySelector('#pbd-chart').parentElement;
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'pbd-loading';
    loadingDiv.className = 'loading-indicator';
    loadingDiv.textContent = 'Loading PBD data from BigQuery...';
    if (pbdCanvas && !document.getElementById('pbd-loading')) {
        pbdContainer.insertBefore(loadingDiv, pbdCanvas);
    }
    
    try {
        console.log(`[Frontend] Fetching PBD data for ${hospital} from ${startDate} to ${endDate}...`);
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 360000); // 6 minute timeout (to match backend 5 min + buffer)
        
        const response = await fetch(
            `/api/pbd-data?hospital_name=${encodeURIComponent(hospital)}&start_date=${startDate}&end_date=${endDate}`,
            { signal: controller.signal }
        );
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log(`[Frontend] PBD data received: ${data.daily_pbd ? data.daily_pbd.length : 0} records`);
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        displayPBDChart(data);
    } catch (error) {
        if (error.name === 'AbortError') {
            console.error('[Frontend] PBD data request timed out after 2.5 minutes');
            loadingDiv.textContent = 'PBD query timed out. Try a shorter date range.';
        } else {
            console.error('[Frontend] Error loading PBD data:', error);
            loadingDiv.textContent = `Error: ${error.message}`;
        }
        // Don't show alert, just log it - PBD is secondary data
        displayPBDChart({ daily_pbd: [] });
    } finally {
        // Remove loading indicator
        const loadingEl = document.getElementById('pbd-loading');
        if (loadingEl) {
            loadingEl.remove();
        }
    }
}

// Display PBD chart
function displayPBDChart(data) {
    const canvas = document.getElementById('pbd-chart');
    if (!canvas) return;
    
    // Check if Chart.js is loaded
    if (typeof Chart === 'undefined') {
        console.error('[Quality Alerts] Chart.js is not loaded! Cannot display PBD chart.');
        return;
    }
    
    const renderingContext = canvas.getContext('2d');
    
    // Destroy existing chart if it exists
    if (pbdChart) {
        pbdChart.destroy();
    }
    
    // Prepare data
    const sortedData = data.daily_pbd.sort((a, b) => new Date(a.date) - new Date(b.date));
    const labels = sortedData.map(d => formatDateLabel(d.date));
    const pbdValues = sortedData.map(d => d.total_pbd);
    
    // Create chart
    pbdChart = new Chart(renderingContext, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Patient Bed Days (PBD)',
                data: pbdValues,
                borderColor: 'rgb(153, 102, 255)',
                backgroundColor: 'rgba(153, 102, 255, 0.2)',
                tension: 0.1,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Daily Patient Bed Days Over Time',
                    font: {
                        size: 18
                    }
                },
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Patient Bed Days'
                    },
                    beginAtZero: true
                }
            }
        }
    });
}

// Load and display raw data
async function loadRawData(hospital, startDate, endDate) {
    console.log('[Frontend] Loading raw data for:', hospital, startDate, 'to', endDate);
    try {
        // Backend returns database data only (no BigQuery), so short timeout is sufficient
        const response = await fetchWithTimeout(
            `/api/raw-data?hospital_name=${encodeURIComponent(hospital)}&start_date=${startDate}&end_date=${endDate}`,
            {},
            30000  // 30 second timeout (sufficient for database queries only)
        );
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('[Frontend] Raw data received:', data.length, 'rows');
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Check for November data
        const today = new Date();
        const currentYear = today.getFullYear();
        const currentMonth = today.getMonth() + 1; // JavaScript months are 0-indexed
        
        const novData = data.filter(row => row.year === currentYear && row.month === currentMonth);
        console.log(`[Frontend] November ${currentYear} data in response:`, novData.length, 'rows');
        if (novData.length > 0) {
            console.log('[Frontend] November data:', novData);
        } else {
            console.log('[Frontend] WARNING: No November data in response!');
            console.log('[Frontend] Available months:', [...new Set(data.map(r => `${r.year}-${r.month.toString().padStart(2, '0')}`))].sort());
        }
        
        displayRawDataTable(data);
    } catch (error) {
        console.error('[Frontend] Error loading raw data:', error);
        displayRawDataTable([]);
    }
}

// Display raw data table
function displayRawDataTable(data) {
    const tbody = document.getElementById('raw-data-table-body');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="no-data">No data available for the selected filters.</td></tr>';
        return;
    }
    
    data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${escapeHtml(row.hospital_name)}</td>
            <td>${escapeHtml(row.month_name)}</td>
            <td>${row.year}</td>
            <td>${row.total_patients}</td>
            <td>${row.deaths}</td>
            <td>${row.mortality_rate.toFixed(2)}%</td>
        `;
        tbody.appendChild(tr);
    });
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Load model results
async function loadModelResults(modelId) {
    console.log('[Quality Alerts] Loading model results for:', modelId);
    
    const resultsContainer = document.getElementById('models-results-container');
    const tableBody = document.getElementById('models-table-body');
    const modelTitle = document.getElementById('model-title');
    
    // Show loading state
    resultsContainer.style.display = 'block';
    tableBody.innerHTML = '<tr><td colspan="13" class="no-data">Loading...</td></tr>';
    
    const modelNames = {
        'model1': 'Model 1: Deaths > Highest (Last 3 months)',
        'model2': 'Model 2: Deaths > Highest (Last 6 months)',
        'model3': 'Model 3: Deaths > Avg + 1SD (Last 3 months)',
        'model4': 'Model 4: Deaths > Avg + 1SD (Last 6 months)',
        'model5': 'Model 5: SMR > Highest (Last 3 months)',
        'model6': 'Model 6: SMR > Highest (Last 6 months)',
        'model7': 'Model 7: SMR > Avg + 1SD (Last 3 months)',
        'model8': 'Model 8: SMR > Avg + 1SD (Last 6 months)',
        'model9': 'Model 9: Mortality % > Highest (Last 3 months)',
        'model10': 'Model 10: Mortality % > Highest (Last 6 months)',
        'model11': 'Model 11: Mortality % > Avg + 1SD (Last 3 months)',
        'model12': 'Model 12: Mortality % > Avg + 1SD (Last 6 months)',
        'model13': 'Model 13: Mortality Rate Increasing (3 Consecutive Months)'
    };
    
    modelTitle.textContent = modelNames[modelId] || 'Model Results';
    
    try {
        // Determine timeout based on model type and complexity
        const isSMRModel = modelId.startsWith('model') && 
                          ['5', '6', '7', '8'].includes(modelId.replace('model', ''));
        // Models using 6 months of data (2, 4, 6, 8, 10, 12) need more time
        const is6MonthModel = modelId.startsWith('model') && 
                             ['2', '4', '6', '8', '10', '12'].includes(modelId.replace('model', ''));
        
        let timeout;
        if (isSMRModel) {
            timeout = 300000;  // 5 minutes for SMR models (need to fetch expected_death_percentage)
        } else if (is6MonthModel) {
            timeout = 120000;  // 2 minutes for 6-month models (more data to process)
        } else {
            timeout = 60000;   // 1 minute for 3-month models
        }
        
        console.log(`[Quality Alerts] Fetching ${modelId} with ${timeout/1000}s timeout...`);
        
        const response = await fetchWithTimeout(
            `/api/models/${modelId}`,
            {},
            timeout
        );
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error(`[Quality Alerts] HTTP error ${response.status}:`, errorText);
            throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
        }
        
        const data = await response.json();
        console.log(`[Quality Alerts] Received data for ${modelId}:`, data.results ? `${data.results.length} results` : 'no results');
        
        if (data.error) {
            console.error(`[Quality Alerts] API returned error:`, data.error);
            throw new Error(data.error);
        }
        
        currentModelResults = data.results || [];
        currentModelId = modelId;
        
        if (!Array.isArray(currentModelResults)) {
            console.error(`[Quality Alerts] Results is not an array:`, typeof currentModelResults);
            throw new Error('Invalid response format: results is not an array');
        }
        
        console.log(`[Quality Alerts] Displaying ${currentModelResults.length} results for ${modelId}`);
        displayModelResults(currentModelResults, modelId);
    } catch (error) {
        console.error('[Quality Alerts] Error loading model results:', error);
        tableBody.innerHTML = `<tr><td colspan="13" class="no-data">Error loading results: ${error.message}</td></tr>`;
        const hospitalCountEl = document.getElementById('hospital-count');
        if (hospitalCountEl) {
            hospitalCountEl.textContent = 'Error loading data';
        }
    }
}

// Display model results
function displayModelResults(results, modelId) {
    const tableBody = document.getElementById('models-table-body');
    const hospitalCountEl = document.getElementById('hospital-count');
    tableBody.innerHTML = '';
    
    // Update hospital count
    const count = results ? results.length : 0;
    hospitalCountEl.textContent = `${count} hospital${count !== 1 ? 's' : ''} found`;
    
    if (!results || results.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="13" class="no-data">No hospitals found that crossed the threshold for this model.</td></tr>';
        hospitalCountEl.textContent = '0 hospitals found';
        return;
    }
    
    results.forEach(result => {
        try {
            const tr = document.createElement('tr');
            const statusClass = result.status === 'Alert' ? 'alert-row' : '';
            tr.className = statusClass;
        
            // Format value and threshold based on model type
            let valueDisplay = '';
            let thresholdDisplay = '';
            
            if (modelId === 'model13') {
                // Model 13: Show trend information
                if (result.trend_info) {
                    const trend = result.trend_info;
                    valueDisplay = `Trend: ${trend.rate1.toFixed(2)}% → ${trend.rate2.toFixed(2)}% → ${trend.rate3.toFixed(2)}%`;
                    thresholdDisplay = `Starting: ${trend.rate1.toFixed(2)}%`;
                } else {
                    valueDisplay = result.mortality_rate !== undefined ? `${result.mortality_rate.toFixed(2)}%` : '-';
                    thresholdDisplay = result.threshold !== undefined ? `${result.threshold.toFixed(2)}%` : '-';
                }
            } else if (modelId.startsWith('model5') || modelId.startsWith('model6') || 
                modelId.startsWith('model7') || modelId.startsWith('model8')) {
                // SMR models
                if (result.smr !== undefined && result.smr !== null && !isNaN(result.smr)) {
                    valueDisplay = `SMR: ${result.smr.toFixed(2)}`;
                } else {
                    valueDisplay = '-';
                }
                thresholdDisplay = result.threshold !== undefined && result.threshold !== null ? result.threshold.toFixed(2) : '-';
            } else if (modelId.startsWith('model9') || modelId.startsWith('model10') || 
                       modelId.startsWith('model11') || modelId.startsWith('model12')) {
                // Percentage models
                valueDisplay = result.mortality_rate !== undefined ? `${result.mortality_rate.toFixed(2)}%` : '-';
                thresholdDisplay = result.threshold !== undefined ? `${result.threshold.toFixed(2)}%` : '-';
            } else {
                // Deaths models (Model 1-4)
                valueDisplay = result.deaths !== undefined ? result.deaths : '-';
                thresholdDisplay = result.threshold !== undefined ? result.threshold.toFixed(0) : '-';
            }
            
            // Format last 6 months mortality as separate columns
            let monthCells = ['-', '-', '-', '-', '-', '-'];
            let monthPeriods = ['-', '-', '-', '-', '-', '-'];
            if (result.last_6_months_mortality && Array.isArray(result.last_6_months_mortality)) {
                result.last_6_months_mortality.forEach((m, index) => {
                    if (index < 6) {
                        const rate = m.mortality_rate !== undefined ? m.mortality_rate.toFixed(2) : '0.00';
                        monthCells[index] = rate;
                        monthPeriods[index] = m.period || '-';
                    }
                });
            }
            
            tr.innerHTML = `
                <td>${escapeHtml(result.hospital_name)}</td>
                <td>${result.current_period || '-'}</td>
                <td>${result.deaths !== undefined ? result.deaths : '-'}</td>
                <td>${result.mortality_rate !== undefined ? result.mortality_rate.toFixed(2) + '%' : '-'}</td>
                <td>${valueDisplay}</td>
                <td>${thresholdDisplay}</td>
                <td><span class="status-badge ${result.status === 'Alert' ? 'alert' : 'normal'}">${result.status || 'Normal'}</span></td>
                <td title="${monthPeriods[0]}">${monthCells[0]}%</td>
                <td title="${monthPeriods[1]}">${monthCells[1]}%</td>
                <td title="${monthPeriods[2]}">${monthCells[2]}%</td>
                <td title="${monthPeriods[3]}">${monthCells[3]}%</td>
                <td title="${monthPeriods[4]}">${monthCells[4]}%</td>
                <td title="${monthPeriods[5]}">${monthCells[5]}%</td>
            `;
            tableBody.appendChild(tr);
        } catch (error) {
            console.error('[Quality Alerts] Error rendering table row for hospital:', result.hospital_name, error);
            // Add error row for this hospital instead of breaking
            const errorRow = document.createElement('tr');
            errorRow.innerHTML = `<td colspan="13" class="no-data">Error rendering data for ${escapeHtml(result.hospital_name || 'unknown')}: ${error.message}</td>`;
            tableBody.appendChild(errorRow);
        }
    });
}

// Download model results as CSV
function downloadModelResultsAsCSV() {
    if (!currentModelResults || currentModelResults.length === 0) {
        alert('No data available to download.');
        return;
    }
    
    const modelNames = {
        'model1': 'Model 1 - Deaths > Highest (Last 3 months)',
        'model2': 'Model 2 - Deaths > Highest (Last 6 months)',
        'model3': 'Model 3 - Deaths > Avg + 1SD (Last 3 months)',
        'model4': 'Model 4 - Deaths > Avg + 1SD (Last 6 months)',
        'model5': 'Model 5 - SMR > Highest (Last 3 months)',
        'model6': 'Model 6 - SMR > Highest (Last 6 months)',
        'model7': 'Model 7 - SMR > Avg + 1SD (Last 3 months)',
        'model8': 'Model 8 - SMR > Avg + 1SD (Last 6 months)',
        'model9': 'Model 9 - Mortality % > Highest (Last 3 months)',
        'model10': 'Model 10 - Mortality % > Highest (Last 6 months)',
        'model11': 'Model 11 - Mortality % > Avg + 1SD (Last 3 months)',
        'model12': 'Model 12 - Mortality % > Avg + 1SD (Last 6 months)',
        'model13': 'Model 13 - Mortality Rate Increasing (3 Consecutive Months)'
    };
    
    const modelName = modelNames[currentModelId] || currentModelId;
    
    // CSV Headers
    const headers = [
        'Hospital',
        'Current Period',
        'Deaths',
        'Mortality Rate (%)',
        'Value',
        'Threshold',
        'Status',
        'Month 1 (%)',
        'Month 2 (%)',
        'Month 3 (%)',
        'Month 4 (%)',
        'Month 5 (%)',
        'Month 6 (%)'
    ];
    
    // Convert results to CSV rows
    const csvRows = [];
    csvRows.push(headers.join(','));
    
    currentModelResults.forEach(result => {
        // Format value and threshold based on model type
        let valueDisplay = '';
        
        if (currentModelId === 'model13') {
            // Model 13: Show trend information
            if (result.trend_info) {
                const trend = result.trend_info;
                valueDisplay = `${trend.rate1.toFixed(2)}% → ${trend.rate2.toFixed(2)}% → ${trend.rate3.toFixed(2)}%`;
            } else {
                valueDisplay = result.mortality_rate !== undefined ? result.mortality_rate.toFixed(2) : '-';
            }
        } else if (currentModelId.startsWith('model5') || currentModelId.startsWith('model6') || 
            currentModelId.startsWith('model7') || currentModelId.startsWith('model8')) {
            valueDisplay = result.smr !== undefined ? result.smr.toFixed(2) : '-';
        } else if (currentModelId.startsWith('model9') || currentModelId.startsWith('model10') || 
                   currentModelId.startsWith('model11') || currentModelId.startsWith('model12')) {
            valueDisplay = result.mortality_rate !== undefined ? result.mortality_rate.toFixed(2) : '-';
        } else {
            valueDisplay = result.deaths !== undefined ? result.deaths : '-';
        }
        
        // Format last 6 months mortality as separate columns
        let monthValues = ['-', '-', '-', '-', '-', '-'];
        if (result.last_6_months_mortality && Array.isArray(result.last_6_months_mortality)) {
            result.last_6_months_mortality.forEach((m, index) => {
                if (index < 6) {
                    const rate = m.mortality_rate !== undefined ? m.mortality_rate.toFixed(2) : '0.00';
                    monthValues[index] = rate;
                }
            });
        }
        
        // Escape commas and quotes in CSV values
        const escapeCsv = (val) => {
            if (val === null || val === undefined) return '';
            const str = String(val);
            if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                return `"${str.replace(/"/g, '""')}"`;
            }
            return str;
        };
        
        const row = [
            escapeCsv(result.hospital_name),
            escapeCsv(result.current_period || '-'),
            escapeCsv(result.deaths !== undefined ? result.deaths : '-'),
            escapeCsv(result.mortality_rate !== undefined ? result.mortality_rate.toFixed(2) : '-'),
            escapeCsv(valueDisplay),
            escapeCsv(result.threshold !== undefined ? result.threshold.toFixed(2) : '-'),
            escapeCsv(result.status || 'Normal'),
            escapeCsv(monthValues[0]),
            escapeCsv(monthValues[1]),
            escapeCsv(monthValues[2]),
            escapeCsv(monthValues[3]),
            escapeCsv(monthValues[4]),
            escapeCsv(monthValues[5])
        ];
        
        csvRows.push(row.join(','));
    });
    
    // Create CSV content
    const csvContent = csvRows.join('\n');
    
    // Create blob and download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    // Generate filename with current date
    const now = new Date();
    const dateStr = now.toISOString().split('T')[0];
    const filename = `${modelName.replace(/[^a-z0-9]/gi, '_')}_${dateStr}.csv`;
    
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Send alert to Google Chat
async function sendAlertToGoogleChat() {
    if (!currentModelId) {
        alert('Please select a model first.');
        return;
    }
    
    const sendBtn = document.getElementById('send-alert-btn');
    const originalText = sendBtn.textContent;
    
    // Disable button and show loading
    sendBtn.disabled = true;
    sendBtn.textContent = '⏳ Sending...';
    
    try {
        const response = await fetch('/api/send-alert', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model_id: currentModelId
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ Alert sent successfully!\n\n${result.message}`);
        } else {
            alert(`❌ Failed to send alert:\n\n${result.message || result.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('[Quality Alerts] Error sending alert:', error);
        alert(`❌ Error sending alert: ${error.message}`);
    } finally {
        // Re-enable button
        sendBtn.disabled = false;
        sendBtn.textContent = originalText;
    }
}

