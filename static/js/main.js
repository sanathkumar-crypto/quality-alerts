// Quality Alerts Dashboard JavaScript
console.log('[Quality Alerts] Script loaded!');

// Global chart instances
let mortalityChart = null;
let pbdChart = null;

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

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('[Quality Alerts] DOM loaded, initializing dashboard...');
    loadHospitals();
    setDefaultDates();
    
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
    console.log('[Quality Alerts] Event listeners attached');
});

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
        const response = await fetchWithTimeout(
            `/api/mortality-data?hospital_name=${encodeURIComponent(hospital)}&start_date=${startDate}&end_date=${endDate}`,
            {},
            10000  // 10 second timeout
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
        const response = await fetch(
            `/api/pbd-data?hospital_name=${encodeURIComponent(hospital)}&start_date=${startDate}&end_date=${endDate}`
        );
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        displayPBDChart(data);
    } catch (error) {
        console.error('Error loading PBD data:', error);
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
    console.log('[Quality Alerts] Loading raw data...');
    try {
        const response = await fetch(
            `/api/raw-data?hospital_name=${encodeURIComponent(hospital)}&start_date=${startDate}&end_date=${endDate}`
        );
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        displayRawDataTable(data);
    } catch (error) {
        console.error('Error loading raw data:', error);
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

