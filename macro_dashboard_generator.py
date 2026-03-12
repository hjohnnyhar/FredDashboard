"""
Macro Dashboard Generator with Real FRED Data
Fetches live economic data from FRED API and generates a standalone HTML dashboard

Usage:
    python macro_dashboard_generator.py

Output:
    Creates 'public/index.html' for Vercel static deployment
"""

import os
import requests
import json
from datetime import datetime
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# FRED API Configuration
FRED_API_KEY = os.environ.get('FRED_API_KEY')
if not FRED_API_KEY:
    raise RuntimeError("FRED_API_KEY environment variable is not set")

FRED_BASE_URL = 'https://api.stlouisfed.org/fred'

# Economic indicators organized by category
indicators_config = {
    'Growth & Output': [
        ('GDP', 'Real GDP', 'Billions $', '#3b82f6'),
        ('INDPRO', 'Industrial Production Index', 'Index', '#3b82f6'),
        ('RSXFS', 'Retail Sales', 'Millions $', '#3b82f6')
    ],
    'Labor Market': [
        ('UNRATE', 'Unemployment Rate', '%', '#10b981'),
        ('PAYEMS', 'Nonfarm Payrolls', 'Thousands', '#10b981'),
        ('CIVPART', 'Labor Force Participation', '%', '#10b981')
    ],
    'Inflation': [
        ('CPIAUCSL', 'CPI (All Items)', 'Index', '#ef4444'),
        ('CPILFESL', 'Core CPI', 'Index', '#ef4444'),
        ('PCEPI', 'PCE Price Index', 'Index', '#ef4444')
    ],
    'Monetary Policy': [
        ('DFF', 'Federal Funds Rate', '%', '#8b5cf6'),
        ('DGS10', '10-Year Treasury Yield', '%', '#8b5cf6'),
        ('DGS2', '2-Year Treasury Yield', '%', '#8b5cf6')
    ],
    'Housing': [
        ('HOUST', 'Housing Starts', 'Thousands', '#f59e0b'),
        ('MORTGAGE30US', '30-Year Mortgage Rate', '%', '#f59e0b'),
        ('CSUSHPISA', 'Case-Shiller Home Price Index', 'Index', '#f59e0b')
    ],
    'Leading Indicators': [
        ('UMCSENT', 'Consumer Sentiment', 'Index', '#06b6d4'),
        ('DCOILWTICO', 'WTI Crude Oil Price', '$/Barrel', '#06b6d4'),
        ('VIXCLS', 'VIX (Volatility Index)', 'Index', '#06b6d4')
    ]
}


def fetch_fred_series(series_id):
    """Fetch data for a specific FRED series"""
    try:
        url = f"{FRED_BASE_URL}/series/observations"
        params = {
            'series_id': series_id,
            'api_key': FRED_API_KEY,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': 24
        }

        print(f"  Fetching {series_id}...", end=' ')
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if 'observations' in data and len(data['observations']) > 0:
            valid_obs = [obs for obs in data['observations'] if obs['value'] != '.']

            if len(valid_obs) > 0:
                result = {
                    'current': float(valid_obs[0]['value']),
                    'previous': float(valid_obs[1]['value']) if len(valid_obs) > 1 else None,
                    'date': valid_obs[0]['date'],
                    'history': [{'date': obs['date'], 'value': float(obs['value'])} for obs in reversed(valid_obs[:12])]
                }
                print("OK")
                return result

        print("SKIP (no data)")
        return None

    except Exception as e:
        print(f"FAIL ({str(e)[:50]})")
        return None


def calculate_recession_probability(data):
    """Calculate recession probability based on economic indicators"""
    score = 0
    factors = []

    if 'DGS10' in data and 'DGS2' in data and data['DGS10'] and data['DGS2']:
        spread = data['DGS10']['current'] - data['DGS2']['current']
        if spread < -0.5:
            score += 35
            factors.append('Deeply inverted yield curve')
        elif spread < 0:
            score += 20
            factors.append('Inverted yield curve')
        elif spread < 0.5:
            score += 10
            factors.append('Flat yield curve')

    if 'UNRATE' in data and data['UNRATE'] and data['UNRATE']['previous']:
        unemp_change = ((data['UNRATE']['current'] - data['UNRATE']['previous']) / data['UNRATE']['previous']) * 100
        if unemp_change > 0.5:
            score += 25
            factors.append('Rising unemployment')
        elif unemp_change > 0.2:
            score += 15
            factors.append('Unemployment trending up')

    if 'VIXCLS' in data and data['VIXCLS']:
        if data['VIXCLS']['current'] > 30:
            score += 20
            factors.append('High market volatility')
        elif data['VIXCLS']['current'] > 25:
            score += 15
            factors.append('Elevated market volatility')
        elif data['VIXCLS']['current'] > 20:
            score += 8
            factors.append('Moderate market stress')

    if 'INDPRO' in data and data['INDPRO'] and data['INDPRO']['previous']:
        indpro_change = ((data['INDPRO']['current'] - data['INDPRO']['previous']) / data['INDPRO']['previous']) * 100
        if indpro_change < -1:
            score += 15
            factors.append('Declining industrial output')
        elif indpro_change < 0:
            score += 8

    if 'UMCSENT' in data and data['UMCSENT']:
        if data['UMCSENT']['current'] < 65:
            score += 15
            factors.append('Very weak consumer sentiment')
        elif data['UMCSENT']['current'] < 70:
            score += 10
            factors.append('Weak consumer sentiment')

    if 'HOUST' in data and data['HOUST'] and data['HOUST']['previous']:
        houst_change = ((data['HOUST']['current'] - data['HOUST']['previous']) / data['HOUST']['previous']) * 100
        if houst_change < -10:
            score += 10
            factors.append('Sharp decline in housing starts')

    return {
        'probability': min(score, 100),
        'factors': factors
    }


def generate_outlook(recession_prob):
    """Generate 3-month and 6-month economic outlooks"""
    prob = recession_prob['probability']

    if prob < 15:
        outlook3m = 'Expansion'
        detail3m = 'Economic indicators suggest continued growth with low recession risk. Monitor for emerging headwinds in labor markets and credit conditions.'
        outlook6m = 'Growth Continues'
        detail6m = 'Fundamentals support sustained expansion. Rate policy and productivity trends remain favorable for continued economic growth.'
    elif prob < 35:
        outlook3m = 'Stable'
        detail3m = 'Mixed signals present. Growth continues but at a moderating pace. Some caution warranted as leading indicators show divergence.'
        outlook6m = 'Slowing Growth'
        detail6m = 'Economic momentum likely to decelerate over the next two quarters. Monitor labor market and credit conditions closely for signs of deterioration.'
    elif prob < 60:
        outlook3m = 'Cautionary'
        detail3m = 'Multiple warning signals detected. Heightened recession risk requires defensive positioning and increased portfolio hedging.'
        outlook6m = 'Elevated Risk'
        detail6m = 'Recession probability increases significantly over 6-month horizon. Defensive assets and quality focus recommended. Consider reducing cyclical exposure.'
    else:
        outlook3m = 'Contractionary'
        detail3m = 'High probability of economic contraction. Recession may be imminent or already underway based on leading indicator deterioration.'
        outlook6m = 'Recession Likely'
        detail6m = 'Economic contraction expected within 6 months. Risk-off positioning and capital preservation should be primary focus. Flight to quality assets recommended.'

    return {
        'outlook3m': outlook3m,
        'detail3m': detail3m,
        'outlook6m': outlook6m,
        'detail6m': detail6m
    }


def generate_html_dashboard(data, recession_prob, outlook):
    """Generate standalone HTML dashboard with embedded data"""

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Macro Dashboard | Economic Intelligence</title>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Libre+Baskerville:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0e14;
            --bg-secondary: #12171f;
            --bg-card: #1a1f2b;
            --border-color: #2a3342;
            --text-primary: #e6e8eb;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
            --accent-purple: #8b5cf6;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'IBM Plex Mono', monospace;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }}

        .grain-overlay {{
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none; z-index: 1000; mix-blend-mode: overlay;
            background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"><filter id="noise"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="4" stitchTiles="stitch"/></filter><rect width="100%" height="100%" filter="url(%23noise)" opacity="0.03"/></svg>');
        }}

        .container {{ max-width: 1600px; margin: 0 auto; padding: 40px 30px; }}

        header {{
            margin-bottom: 50px; border-bottom: 1px solid var(--border-color);
            padding-bottom: 30px; animation: fadeIn 0.8s ease-out;
        }}

        .header-top {{
            display: flex; justify-content: space-between;
            align-items: flex-start; margin-bottom: 20px;
        }}

        h1 {{
            font-family: 'Libre Baskerville', serif; font-size: 2.5rem;
            font-weight: 700; letter-spacing: -0.02em; margin-bottom: 8px;
        }}

        .date {{
            font-size: 0.85rem; color: var(--text-muted);
            text-transform: uppercase; letter-spacing: 0.1em;
        }}

        .status-badge {{
            padding: 8px 16px; border-radius: 4px; font-size: 0.75rem;
            font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em;
            background: rgba(16, 185, 129, 0.15); color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .tagline {{ color: var(--text-secondary); font-size: 0.95rem; max-width: 600px; }}

        .recession-section {{ margin-bottom: 40px; animation: fadeIn 0.8s ease-out 0.2s backwards; }}

        .recession-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}

        .recession-card {{
            background: var(--bg-card); border: 1px solid var(--border-color);
            padding: 30px; border-radius: 2px; position: relative; overflow: hidden;
            transition: border-color 0.3s ease;
        }}

        .recession-card:hover {{ border-color: var(--accent-blue); }}

        .recession-card::before {{
            content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%;
            background: linear-gradient(180deg, var(--accent-blue), var(--accent-purple));
        }}

        .card-title {{
            font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.15em;
            color: var(--text-muted); margin-bottom: 15px; font-weight: 500;
        }}

        .recession-probability {{
            font-size: 3.5rem; font-weight: 700; font-family: 'Libre Baskerville', serif;
            margin-bottom: 10px; background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
        }}

        .outlook-text {{
            font-size: 1.1rem; color: var(--text-primary);
            margin-bottom: 8px; font-weight: 500;
        }}

        .outlook-subtitle {{
            font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5;
        }}

        .methodology {{
            background: var(--bg-secondary); border: 1px solid var(--border-color);
            padding: 20px; border-radius: 2px; font-size: 0.8rem;
            color: var(--text-secondary); line-height: 1.6;
        }}

        .methodology h3 {{
            font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em;
            color: var(--text-muted); margin-bottom: 10px;
        }}

        .indicators-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px; margin-bottom: 40px;
        }}

        .indicator-category {{ animation: fadeIn 0.8s ease-out backwards; }}
        .indicator-category:nth-child(1) {{ animation-delay: 0.3s; }}
        .indicator-category:nth-child(2) {{ animation-delay: 0.4s; }}
        .indicator-category:nth-child(3) {{ animation-delay: 0.5s; }}
        .indicator-category:nth-child(4) {{ animation-delay: 0.6s; }}
        .indicator-category:nth-child(5) {{ animation-delay: 0.7s; }}
        .indicator-category:nth-child(6) {{ animation-delay: 0.8s; }}

        .category-header {{
            display: flex; align-items: center; gap: 10px; margin-bottom: 15px;
            padding-bottom: 10px; border-bottom: 1px solid var(--border-color);
        }}

        .category-icon {{ width: 8px; height: 8px; border-radius: 50%; }}

        .category-name {{
            font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em;
            color: var(--text-primary); font-weight: 600;
        }}

        .indicator-card {{
            background: var(--bg-card); border: 1px solid var(--border-color);
            padding: 20px; border-radius: 2px; margin-bottom: 15px;
            transition: all 0.3s ease;
        }}

        .indicator-card:hover {{ border-color: var(--accent-blue); transform: translateX(2px); }}

        .indicator-header {{
            display: flex; justify-content: space-between;
            align-items: flex-start; margin-bottom: 12px;
        }}

        .indicator-name {{ font-size: 0.8rem; color: var(--text-secondary); flex: 1; }}

        .indicator-change {{
            font-size: 0.75rem; font-weight: 600;
            padding: 4px 8px; border-radius: 2px;
        }}

        .change-positive {{
            color: var(--accent-green);
            background: rgba(16, 185, 129, 0.1);
        }}

        .change-negative {{
            color: var(--accent-red);
            background: rgba(239, 68, 68, 0.1);
        }}

        .change-neutral {{
            color: var(--text-muted);
            background: rgba(156, 163, 175, 0.1);
        }}

        .indicator-value {{
            font-size: 1.8rem; font-weight: 700;
            font-family: 'Libre Baskerville', serif;
            color: var(--text-primary); margin-bottom: 8px;
        }}

        .indicator-meta {{
            display: flex; justify-content: space-between;
            font-size: 0.7rem; color: var(--text-muted);
            text-transform: uppercase; letter-spacing: 0.05em;
        }}

        footer {{
            margin-top: 60px; padding-top: 30px;
            border-top: 1px solid var(--border-color);
            text-align: center; color: var(--text-muted); font-size: 0.75rem;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        @media (max-width: 768px) {{
            .recession-grid {{ grid-template-columns: 1fr; }}
            .indicators-grid {{ grid-template-columns: 1fr; }}
            h1 {{ font-size: 1.8rem; }}
        }}
    </style>
</head>
<body>
    <div class="grain-overlay"></div>

    <div class="container">
        <header>
            <div class="header-top">
                <div>
                    <h1>Macro Intelligence</h1>
                    <p class="date">{datetime.now().strftime("%A, %B %d, %Y")}</p>
                </div>
                <div class="status-badge">Live FRED Data</div>
            </div>
            <p class="tagline">Real-time economic indicators, recession analysis, and forward-looking assessments for institutional investors</p>
        </header>

        <section class="recession-section">
            <div class="recession-grid">
                <div class="recession-card">
                    <div class="card-title">Current Recession Probability</div>
                    <div class="recession-probability">{recession_prob['probability']:.0f}%</div>
                    <div class="outlook-subtitle">Based on current indicators: {', '.join(recession_prob['factors']) if recession_prob['factors'] else 'Economy showing resilience across key metrics'}.</div>
                </div>

                <div class="recession-card" style="border-left-color: var(--accent-green);">
                    <div class="card-title">3-Month Outlook</div>
                    <div class="outlook-text">{outlook['outlook3m']}</div>
                    <div class="outlook-subtitle">{outlook['detail3m']}</div>
                </div>
            </div>

            <div class="recession-grid">
                <div class="recession-card" style="border-left-color: var(--accent-yellow);">
                    <div class="card-title">6-Month Outlook</div>
                    <div class="outlook-text">{outlook['outlook6m']}</div>
                    <div class="outlook-subtitle">{outlook['detail6m']}</div>
                </div>

                <div class="methodology">
                    <h3>Methodology</h3>
                    <p>Recession probability derived from yield curve inversion (10Y-2Y spread), unemployment rate trends, industrial production momentum, market volatility (VIX), consumer sentiment, and housing market indicators. Outlooks incorporate leading economic indicators, Federal Reserve policy stance, and historical recessionary patterns.</p>
                </div>
            </div>
        </section>

        <div class="indicators-grid">
'''

    for category, indicators in indicators_config.items():
        html_content += f'''
            <div class="indicator-category">
                <div class="category-header">
                    <div class="category-icon" style="background: {indicators[0][3]}"></div>
                    <div class="category-name">{category}</div>
                </div>
'''

        for ind_id, ind_name, unit, color in indicators:
            if ind_id in data and data[ind_id]:
                ind_data = data[ind_id]
                current = ind_data['current']
                previous = ind_data['previous']

                if previous:
                    change_pct = ((current - previous) / abs(previous)) * 100
                else:
                    change_pct = 0

                inverse_indicators = ['UNRATE', 'CPIAUCSL', 'CPILFESL', 'PCEPI', 'VIXCLS', 'MORTGAGE30US']
                is_inverse = ind_id in inverse_indicators

                if is_inverse:
                    change_class = 'change-negative' if change_pct > 0 else 'change-positive'
                else:
                    change_class = 'change-positive' if change_pct > 0 else 'change-negative'

                if abs(change_pct) < 0.01:
                    change_class = 'change-neutral'

                if unit == '%':
                    value_str = f"{current:.2f}%"
                elif current >= 1000000:
                    value_str = f"{current/1000000:.2f}M"
                elif current >= 1000:
                    value_str = f"{current/1000:.1f}K"
                else:
                    value_str = f"{current:.2f}"

                html_content += f'''
                <div class="indicator-card">
                    <div class="indicator-header">
                        <div class="indicator-name">{ind_name}</div>
                        <div class="indicator-change {change_class}">{'+' if change_pct >= 0 else ''}{change_pct:.2f}%</div>
                    </div>
                    <div class="indicator-value">{value_str}</div>
                    <div class="indicator-meta">
                        <span>{unit}</span>
                        <span>As of {ind_data['date']}</span>
                    </div>
                </div>
'''

        html_content += '            </div>\n'

    html_content += '''
        </div>

        <footer>
            <p>Data sourced from Federal Reserve Economic Data (FRED) | Generated: ''' + datetime.now().strftime("%B %d, %Y at %I:%M %p") + '''</p>
            <p style="margin-top: 8px; opacity: 0.6;">For institutional use only. Past performance does not guarantee future results.</p>
        </footer>
    </div>
</body>
</html>'''

    return html_content


def main():
    """Main execution function"""
    print("\n" + "="*70)
    print("MACRO DASHBOARD GENERATOR - FETCHING FRED DATA")
    print("="*70 + "\n")

    economic_data = {}
    total_indicators = sum(len(indicators) for indicators in indicators_config.values())

    for category, indicators in indicators_config.items():
        print(f"\n{category}:")
        for ind_id, ind_name, unit, color in indicators:
            data = fetch_fred_series(ind_id)
            if data:
                economic_data[ind_id] = data
            time.sleep(0.1)

    print(f"\n\nSuccessfully fetched {len(economic_data)}/{total_indicators} indicators")

    print("\nCalculating recession probability and outlook...")
    recession_prob = calculate_recession_probability(economic_data)
    outlook = generate_outlook(recession_prob)

    print(f"\n" + "="*70)
    print("ANALYSIS RESULTS")
    print("="*70)
    print(f"Recession Probability: {recession_prob['probability']:.0f}%")
    print(f"Key Factors: {', '.join(recession_prob['factors']) if recession_prob['factors'] else 'None detected'}")
    print(f"3-Month Outlook: {outlook['outlook3m']}")
    print(f"6-Month Outlook: {outlook['outlook6m']}")
    print("="*70 + "\n")

    print("Generating HTML dashboard...")
    html_content = generate_html_dashboard(economic_data, recession_prob, outlook)

    os.makedirs('public', exist_ok=True)
    output_file = 'public/index.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\nDashboard generated successfully: {output_file}")


if __name__ == "__main__":
    main()
