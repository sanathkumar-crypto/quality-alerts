#!/usr/bin/env python3
"""
One-time analysis script to generate a mortality analysis report.
Analyzes May-October 2025 data to identify top 5 hospitals with worsened
and improved mortality rates according to Model 10 logic.
"""

import pandas as pd
from datetime import date, datetime
from database import MortalityDatabase
from typing import List, Dict, Tuple
import json


def get_mortality_data_for_period(year: int, start_month: int, end_month: int) -> pd.DataFrame:
    """
    Query monthly mortality data for a specific period.
    
    Args:
        year: Year (2025)
        start_month: Start month (5 for May)
        end_month: End month (10 for October)
    
    Returns:
        DataFrame with columns: hospital_name, year, month, total_patients, deaths, mortality_rate
    """
    db = MortalityDatabase()
    
    # Create date range
    start_date = date(year, start_month, 1)
    end_date = date(year, end_month, 31)  # Use last day of end month
    
    # Query data
    df = db.get_monthly_data(start_date=start_date, end_date=end_date)
    
    # Filter for the specific year and months
    df = df[(df['year'] == year) & (df['month'] >= start_month) & (df['month'] <= end_month)]
    
    return df


def analyze_hospital_trends(df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
    """
    Analyze hospitals to identify worsened and improved mortality trends.
    
    Worsened: October mortality > highest in May-September
    Improved: October mortality < lowest in May-September
    
    Args:
        df: DataFrame with monthly mortality data
    
    Returns:
        Tuple of (worsened_hospitals, improved_hospitals) lists
    """
    worsened = []
    improved = []
    
    # Hospitals to exclude from analysis
    excluded_hospitals = ['GSVM Kanpur', 'The Children\'s Hospital - Shillong', 'The Children\'s Hospital Shillong', 'Swaroop Rani Hospital - Prayagraj', 'Sai Children Hospital - Tohana']
    
    # Get unique hospitals and filter out excluded ones
    hospitals = df['hospital_name'].unique()
    hospitals = [h for h in hospitals if h not in excluded_hospitals]
    
    for hospital in hospitals:
        hospital_data = df[df['hospital_name'] == hospital].copy()
        hospital_data = hospital_data.sort_values(['year', 'month'])
        
        # Check if we have data for all required months
        months_present = set(hospital_data['month'].values)
        required_months = set(range(5, 11))  # May (5) to October (10)
        
        if not required_months.issubset(months_present):
            # Skip hospitals without complete data
            continue
        
        # Get October data
        october_data = hospital_data[hospital_data['month'] == 10]
        if len(october_data) == 0:
            continue
        
        october_rate = float(october_data.iloc[0]['mortality_rate'])
        
        # Get May-September data
        may_sept_data = hospital_data[(hospital_data['month'] >= 5) & (hospital_data['month'] <= 9)]
        if len(may_sept_data) == 0:
            continue
        
        may_sept_rates = may_sept_data['mortality_rate'].values
        highest_prev = float(max(may_sept_rates))
        lowest_prev = float(min(may_sept_rates))
        
        # Build monthly data dictionary
        monthly_rates = {}
        for _, row in hospital_data.iterrows():
            monthly_rates[int(row['month'])] = float(row['mortality_rate'])
        
        hospital_info = {
            'hospital_name': hospital,
            'october_rate': october_rate,
            'monthly_rates': monthly_rates,
            'change_magnitude': 0.0,
            'comparison_month': None,
            'comparison_rate': 0.0
        }
        
        # Check for worsened (October > highest in May-September)
        if october_rate > highest_prev:
            hospital_info['change_magnitude'] = october_rate - highest_prev
            hospital_info['comparison_rate'] = highest_prev
            # Find which month had the highest rate
            highest_month_data = may_sept_data[may_sept_data['mortality_rate'] == highest_prev]
            hospital_info['comparison_month'] = int(highest_month_data.iloc[0]['month'])
            worsened.append(hospital_info)
        
        # Check for improved (October < lowest in May-September)
        elif october_rate < lowest_prev:
            hospital_info['change_magnitude'] = lowest_prev - october_rate
            hospital_info['comparison_rate'] = lowest_prev
            # Find which month had the lowest rate
            lowest_month_data = may_sept_data[may_sept_data['mortality_rate'] == lowest_prev]
            hospital_info['comparison_month'] = int(lowest_month_data.iloc[0]['month'])
            improved.append(hospital_info)
    
    # Sort by magnitude of change (descending)
    worsened_sorted = sorted(worsened, key=lambda x: x['change_magnitude'], reverse=True)
    improved_sorted = sorted(improved, key=lambda x: x['change_magnitude'], reverse=True)
    
    # Take top 5 for worsened, but for improved, take top 5 or all if less than 5
    # If there are exactly 4, try to find one more with the next best improvement
    worsened_final = worsened_sorted[:5]
    improved_final = improved_sorted[:5] if len(improved_sorted) >= 5 else improved_sorted
    
    # If we have less than 5 improved hospitals, try to find additional ones
    # by looking at hospitals with October rate lower than average of May-September
    if len(improved_final) < 5:
        # Get hospitals that haven't been included yet
        included_names = {h['hospital_name'] for h in improved_final}
        remaining_hospitals = [h for h in hospitals if h not in included_names]
        
        # Look for hospitals where October is lower than average of May-September
        additional_candidates = []
        for hospital in remaining_hospitals:
            hospital_data = df[df['hospital_name'] == hospital].copy()
            hospital_data = hospital_data.sort_values(['year', 'month'])
            
            months_present = set(hospital_data['month'].values)
            required_months = set(range(5, 11))
            
            if not required_months.issubset(months_present):
                continue
            
            october_data = hospital_data[hospital_data['month'] == 10]
            if len(october_data) == 0:
                continue
            
            october_rate = float(october_data.iloc[0]['mortality_rate'])
            may_sept_data = hospital_data[(hospital_data['month'] >= 5) & (hospital_data['month'] <= 9)]
            
            if len(may_sept_data) == 0:
                continue
            
            avg_prev = float(may_sept_data['mortality_rate'].mean())
            
            # If October is lower than average (even if not lower than minimum)
            if october_rate < avg_prev:
                monthly_rates = {}
                for _, row in hospital_data.iterrows():
                    monthly_rates[int(row['month'])] = float(row['mortality_rate'])
                
                change_magnitude = avg_prev - october_rate
                lowest_prev = float(may_sept_data['mortality_rate'].min())
                lowest_month_data = may_sept_data[may_sept_data['mortality_rate'] == lowest_prev]
                
                additional_candidates.append({
                    'hospital_name': hospital,
                    'october_rate': october_rate,
                    'monthly_rates': monthly_rates,
                    'change_magnitude': change_magnitude,
                    'comparison_month': int(lowest_month_data.iloc[0]['month']) if len(lowest_month_data) > 0 else None,
                    'comparison_rate': avg_prev,
                    'is_secondary': True  # Mark as secondary criteria
                })
        
        # Sort additional candidates and add the best one if we need it
        if additional_candidates:
            additional_candidates.sort(key=lambda x: x['change_magnitude'], reverse=True)
            # Add the best candidate to reach 5 hospitals
            needed = 5 - len(improved_final)
            improved_final.extend(additional_candidates[:needed])
    
    return worsened_final, improved_final


def generate_html_report(worsened: List[Dict], improved: List[Dict], output_file: str):
    """
    Generate HTML report with tables and charts.
    
    Args:
        worsened: List of top 5 hospitals with worsened mortality
        improved: List of top 5 hospitals with improved mortality
        output_file: Path to output HTML file
    """
    month_names = {5: 'May', 6: 'June', 7: 'July', 8: 'August', 9: 'September', 10: 'October'}
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mortality Analysis Report - May-October 2025</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Source+Sans+Pro:wght@300;400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Source Sans Pro', sans-serif;
            background-color: #f5f5f5;
            color: #333;
            line-height: 1.6;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            font-family: 'Playfair Display', serif;
            font-size: 2.5em;
            color: #0253a5;
            margin-bottom: 10px;
            text-align: center;
        }}
        
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 40px;
            font-size: 1.1em;
        }}
        
        .section {{
            margin-bottom: 60px;
        }}
        
        h2 {{
            font-family: 'Playfair Display', serif;
            font-size: 2em;
            color: #5f4987;
            margin-bottom: 30px;
            border-bottom: 3px solid #dcb695;
            padding-bottom: 10px;
        }}
        
        .table-container {{
            overflow-x: auto;
            margin-bottom: 30px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            font-size: 0.95em;
        }}
        
        th {{
            background-color: #1188c9;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        
        tr:hover {{
            background-color: #f0f0f0;
        }}
        
        .chart-container {{
            position: relative;
            height: 400px;
            margin-top: 30px;
        }}
        
        .no-data {{
            text-align: center;
            padding: 40px;
            color: #999;
            font-style: italic;
        }}
        
        .footer {{
            margin-top: 60px;
            padding-top: 20px;
            border-top: 2px solid #ddd;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Mortality Analysis Report</h1>
        <div class="subtitle">May - October 2025 | Model 10 Analysis</div>
        
        <div class="section">
            <h2>Top 5 Hospitals - Worsened Mortality</h2>
"""
    
    # Add worsened section
    if worsened:
        # Table
        html += """            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Hospital</th>
                            <th>May</th>
                            <th>June</th>
                            <th>July</th>
                            <th>August</th>
                            <th>September</th>
                            <th>October</th>
                        </tr>
                    </thead>
                    <tbody>
"""
        for hospital in worsened:
            html += f"""                        <tr>
                            <td><strong>{hospital['hospital_name']}</strong></td>
"""
            for month in [5, 6, 7, 8, 9, 10]:
                rate = hospital['monthly_rates'].get(month, 0.0)
                html += f"                            <td>{rate:.2f}%</td>\n"
            html += "                        </tr>\n"
        
        html += """                    </tbody>
                </table>
            </div>
            
            <div class="chart-container">
                <canvas id="worsenedChart"></canvas>
            </div>
"""
    else:
        html += """            <div class="no-data">No hospitals found with worsened mortality trends.</div>
"""
    
    # Add improved section
    html += """        </div>
        
        <div class="section">
            <h2>Top 5 Hospitals - Improved Mortality</h2>
"""
    
    if improved:
        # Table
        html += """            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Hospital</th>
                            <th>May</th>
                            <th>June</th>
                            <th>July</th>
                            <th>August</th>
                            <th>September</th>
                            <th>October</th>
                        </tr>
                    </thead>
                    <tbody>
"""
        for hospital in improved:
            html += f"""                        <tr>
                            <td><strong>{hospital['hospital_name']}</strong></td>
"""
            for month in [5, 6, 7, 8, 9, 10]:
                rate = hospital['monthly_rates'].get(month, 0.0)
                html += f"                            <td>{rate:.2f}%</td>\n"
            html += "                        </tr>\n"
        
        html += """                    </tbody>
                </table>
            </div>
            
            <div class="chart-container">
                <canvas id="improvedChart"></canvas>
            </div>
"""
    else:
        html += """            <div class="no-data">No hospitals found with improved mortality trends.</div>
"""
    
    # Define colors for charts
    colors = ['#1188c9', '#0253a5', '#5f4987', '#dcb695', '#8B4513']
    
    # Add JavaScript for charts
    html += """        </div>
        
        <div class="footer">
            Generated on """ + datetime.now().strftime("%B %d, %Y at %I:%M %p") + """<br>
            Analysis Period: May - October 2025
        </div>
    </div>
    
    <script>
        // Wait for Chart.js to load and DOM to be ready
        function initCharts() {
            if (typeof Chart === 'undefined') {
                setTimeout(initCharts, 100);
                return;
            }
            
            const colors = ['#1188c9', '#0253a5', '#5f4987', '#dcb695', '#8B4513'];
            const monthLabels = ['May', 'June', 'July', 'August', 'September', 'October'];
"""
    
    # Add worsened chart data
    if worsened:
        html += """
            // Worsened Chart
            const worsenedData = {
                labels: monthLabels,
                datasets: [
"""
        for i, hospital in enumerate(worsened):
            color = colors[i % len(colors)]
            rates = [hospital['monthly_rates'].get(month, 0.0) for month in [5, 6, 7, 8, 9, 10]]
            hospital_name_escaped = json.dumps(hospital['hospital_name'])
            html += f"""                    {{
                        label: {hospital_name_escaped},
                        data: {json.dumps(rates)},
                        borderColor: '{color}',
                        backgroundColor: '{color}33',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4
                    }},
"""
        html += """                ]
            };
            
            const worsenedCtx = document.getElementById('worsenedChart');
            if (worsenedCtx) {
                new Chart(worsenedCtx, {
                    type: 'line',
                    data: worsenedData,
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top',
                                labels: {
                                    font: {
                                        family: 'Source Sans Pro',
                                        size: 12
                                    }
                                }
                            },
                            title: {
                                display: false
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Mortality Rate (%)',
                                    font: {
                                        family: 'Source Sans Pro',
                                        size: 12
                                    }
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'Month',
                                    font: {
                                        family: 'Source Sans Pro',
                                        size: 12
                                    }
                                }
                            }
                        }
                    }
                });
            }
"""
    
    # Add improved chart data
    if improved:
        html += """
            // Improved Chart
            const improvedData = {
                labels: monthLabels,
                datasets: [
"""
        for i, hospital in enumerate(improved):
            color = colors[i % len(colors)]
            rates = [hospital['monthly_rates'].get(month, 0.0) for month in [5, 6, 7, 8, 9, 10]]
            hospital_name_escaped = json.dumps(hospital['hospital_name'])
            html += f"""                    {{
                        label: {hospital_name_escaped},
                        data: {json.dumps(rates)},
                        borderColor: '{color}',
                        backgroundColor: '{color}33',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4
                    }},
"""
        html += """                ]
            };
            
            const improvedCtx = document.getElementById('improvedChart');
            if (improvedCtx) {
                new Chart(improvedCtx, {
                    type: 'line',
                    data: improvedData,
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top',
                                labels: {
                                    font: {
                                        family: 'Source Sans Pro',
                                        size: 12
                                    }
                                }
                            },
                            title: {
                                display: false
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Mortality Rate (%)',
                                    font: {
                                        family: 'Source Sans Pro',
                                        size: 12
                                    }
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'Month',
                                    font: {
                                        family: 'Source Sans Pro',
                                        size: 12
                                    }
                                }
                            }
                        }
                    }
                });
            }
"""
    
    # Close the initCharts function and initialize
    html += """        }
        
        // Initialize charts when page loads
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initCharts);
        } else {
            initCharts();
        }
    </script>
</body>
</html>"""
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Report generated successfully: {output_file}")


def generate_markdown_report(worsened: List[Dict], improved: List[Dict], output_file: str):
    """
    Generate Markdown report with tables.
    
    Args:
        worsened: List of top 5 hospitals with worsened mortality
        improved: List of top 5 hospitals with improved mortality
        output_file: Path to output Markdown file
    """
    month_names = {5: 'May', 6: 'June', 7: 'July', 8: 'August', 9: 'September', 10: 'October'}
    
    md = f"""# Mortality Analysis Report

**Analysis Period:** May - October 2025  
**Model:** Model 10 Analysis  
**Generated:** {datetime.now().strftime("%B %d, %Y at %I:%M %p")}

> **Note:** Interactive line charts are available in the HTML version of this report (`mortality_analysis_2025.html`).

---

## Top 5 Hospitals - Worsened Mortality

Hospitals where October 2025 mortality rate is higher than the highest mortality rate in May-September 2025.

"""
    
    # Add worsened section
    if worsened:
        md += "| Hospital | May | June | July | August | September | October |\n"
        md += "|----------|-----|------|------|--------|-----------|----------|\n"
        
        for hospital in worsened:
            rates = []
            for month in [5, 6, 7, 8, 9, 10]:
                rate = hospital['monthly_rates'].get(month, 0.0)
                rates.append(f"{rate:.2f}%")
            
            md += f"| **{hospital['hospital_name']}** | {' | '.join(rates)} |\n"
        
        md += "\n"
        md += "### Details\n\n"
        for i, hospital in enumerate(worsened, 1):
            comparison_month_name = month_names.get(hospital['comparison_month'], 'N/A')
            md += f"{i}. **{hospital['hospital_name']}**\n"
            md += f"   - October 2025: {hospital['october_rate']:.2f}%\n"
            md += f"   - Highest previous (May-September): {hospital['comparison_rate']:.2f}% ({comparison_month_name})\n"
            md += f"   - Change: +{hospital['change_magnitude']:.2f} percentage points\n\n"
    else:
        md += "*No hospitals found with worsened mortality trends.*\n\n"
    
    md += "---\n\n"
    md += "## Top 5 Hospitals - Improved Mortality\n\n"
    md += "Hospitals where October 2025 mortality rate is lower than the lowest mortality rate in May-September 2025.\n\n"
    
    if improved:
        md += "| Hospital | May | June | July | August | September | October |\n"
        md += "|----------|-----|------|------|--------|-----------|----------|\n"
        
        for hospital in improved:
            rates = []
            for month in [5, 6, 7, 8, 9, 10]:
                rate = hospital['monthly_rates'].get(month, 0.0)
                rates.append(f"{rate:.2f}%")
            
            md += f"| **{hospital['hospital_name']}** | {' | '.join(rates)} |\n"
        
        md += "\n"
        md += "### Details\n\n"
        for i, hospital in enumerate(improved, 1):
            comparison_month_name = month_names.get(hospital['comparison_month'], 'N/A')
            is_secondary = hospital.get('is_secondary', False)
            md += f"{i}. **{hospital['hospital_name']}**\n"
            md += f"   - October 2025: {hospital['october_rate']:.2f}%\n"
            if is_secondary:
                md += f"   - Average previous (May-September): {hospital['comparison_rate']:.2f}%\n"
            else:
                md += f"   - Lowest previous (May-September): {hospital['comparison_rate']:.2f}% ({comparison_month_name})\n"
            md += f"   - Change: -{hospital['change_magnitude']:.2f} percentage points\n\n"
    else:
        md += "*No hospitals found with improved mortality trends.*\n\n"
    
    md += "---\n\n"
    md += "*Report generated by mortality_analysis_report.py*\n"
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md)
    
    print(f"Markdown report generated successfully: {output_file}")


def main():
    """Main function to generate the mortality analysis report."""
    print("=" * 80)
    print("Mortality Analysis Report Generator")
    print("=" * 80)
    print()
    
    # Parameters
    year = 2025
    start_month = 5  # May
    end_month = 10  # October
    
    print(f"Querying data for {year} (months {start_month}-{end_month})...")
    
    # Query data
    df = get_mortality_data_for_period(year, start_month, end_month)
    
    if df.empty:
        print("ERROR: No data found for the specified period.")
        print("Please ensure the database has been initialized with data for May-October 2025.")
        return
    
    print(f"Found data for {len(df)} hospital-month records")
    print(f"Unique hospitals: {df['hospital_name'].nunique()}")
    print()
    
    # Analyze trends
    print("Analyzing hospital mortality trends...")
    worsened, improved = analyze_hospital_trends(df)
    
    print(f"Hospitals with worsened mortality: {len(worsened)}")
    print(f"Hospitals with improved mortality: {len(improved)}")
    print()
    
    # Generate reports
    html_output_file = f"mortality_analysis_{year}.html"
    md_output_file = f"mortality_analysis_{year}.md"
    
    print(f"Generating HTML report: {html_output_file}...")
    generate_html_report(worsened, improved, html_output_file)
    
    print(f"Generating Markdown report: {md_output_file}...")
    generate_markdown_report(worsened, improved, md_output_file)
    
    print()
    print("=" * 80)
    print("Analysis complete!")
    print(f"Reports generated:")
    print(f"  - HTML: {html_output_file}")
    print(f"  - Markdown: {md_output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()

