import requests
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, HourLocator
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import formatdate
import smtplib
from datetime import datetime, timedelta

import numpy as np
from scipy.signal import savgol_filter
import io

# Constants
NOAA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
WEATHER_URL = "https://api.weather.gov/gridpoints/SEW/106,72/forecast"
EMAIL_SENDER = 'beyera13@gmail.com'
EMAIL_RECEIVER = 'beyera13@gmail.com'
EMAIL_PASSWORD = 'tdxm jolt btqs wpeu'


# Function to fetch tide data
def fetch_tide_data():
    params = {
        "station": "9414863",
        "product": "predictions",
        "date": "today",
        "datum": "MLLW",
        "units": "english",
        "time_zone": "lst_ldt",
        "format": "json"
    }
    response = requests.get(NOAA_URL, params=params)
    tide_data = response.json()
    return tide_data


# Function to fetch 7-day weather forecast
def fetch_7day_forecast():
    response = requests.get(WEATHER_URL)
    weather_data = response.json()
    periods = weather_data['properties']['periods']
    forecast = []

    for period in periods:
        date = period['startTime']
        temperature = period['temperature']
        wind_speed = int(period['windSpeed'].split()[0])
        weather_conditions = period['shortForecast']
        forecast.append({
            'date': date,
            'temperature': temperature,
            'wind_speed': wind_speed,
            'conditions': weather_conditions
        })

    return forecast


# Function to evaluate kayak conditions using tide data
def evaluate_kayak_conditions(tide_times):
    now = datetime.now()

    ideal_morning_start = now.replace(hour=7, minute=0, second=0, microsecond=0)
    ideal_morning_end = now.replace(hour=11, minute=0, second=0, microsecond=0)
    ideal_evening_start = now.replace(hour=16, minute=0, second=0, microsecond=0)
    ideal_evening_end = now.replace(hour=19, minute=0, second=0, microsecond=0)

    # Check tide conditions
    tide_status = 'Poor'
    for tide_time in tide_times:
        if (ideal_morning_start <= tide_time <= ideal_morning_end) or \
                (ideal_evening_start <= tide_time <= ideal_evening_end):
            tide_status = 'GREAT'
            break
        elif (ideal_morning_start - timedelta(hours=1) <= tide_time <= ideal_morning_end + timedelta(hours=1)) or \
                (ideal_evening_start - timedelta(hours=1) <= tide_time <= ideal_evening_end + timedelta(hours=1)):
            tide_status = 'GOOD'

    return tide_status


# Function to plot tide chart
def plot_tide_chart(tide_data):
    predictions = tide_data['predictions']
    times = []
    heights = []

    for p in predictions:
        time = datetime.strptime(p['t'], "%Y-%m-%d %H:%M")
        times.append(time)
        heights.append(float(p['v']))

    times = np.array(times)
    heights = np.array(heights)
    smoothed_heights = savgol_filter(heights, window_length=5, polyorder=2)

    switches = []
    n = len(smoothed_heights)

    for i in range(1, n - 1):
        if smoothed_heights[i - 1] < smoothed_heights[i] > smoothed_heights[i + 1]:
            switches.append((i, 'high'))
        elif smoothed_heights[i - 1] > smoothed_heights[i] < smoothed_heights[i + 1]:
            switches.append((i, 'low'))

    low_tides = [i for i, t in switches if t == 'low']
    high_tides = [i for i, t in switches if t == 'high']
    low_tide_labels = low_tides[:2]
    high_tide_labels = high_tides[:2]

    plt.figure(figsize=(12, 6))
    plt.plot(times, heights, color='b', label='Tide Height')
    plt.plot(times, smoothed_heights, color='b', linestyle='--', label='Smoothed Tide Height')

    for idx in low_tide_labels:
        plt.plot(times[idx], heights[idx], 'go')
        plt.text(times[idx], heights[idx], f'Low Tide {low_tide_labels.index(idx) + 1}\n{heights[idx]:.2f} ft',
                 color='black', ha='right')

    for idx in high_tide_labels:
        plt.plot(times[idx], heights[idx], 'ro')
        plt.text(times[idx], heights[idx], f'High Tide {high_tide_labels.index(idx) + 1}\n{heights[idx]:.2f} ft',
                 color='black', ha='left')

    today_date = datetime.now().strftime('%Y-%m-%d')
    plt.title(f'Tide Predictions with Switches for {today_date}')
    plt.xlabel('Time')
    plt.ylabel('Tide Height (ft)')
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(DateFormatter('%H:%M'))
    plt.gca().xaxis.set_major_locator(HourLocator(interval=1))
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save to a BytesIO object
    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png')
    img_stream.seek(0)
    plt.close()
    return img_stream


# Function to send email
def send_email(subject, body, img_stream):
    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Date'] = formatdate(localtime=True)

    msg.attach(MIMEText(body, 'html'))

    # Attach the image
    img = MIMEImage(img_stream.read(), name='tide_chart.png')
    img.add_header('Content-ID', '<tide_chart>')
    msg.attach(img)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)


# Main function
def main():
    tide_data = fetch_tide_data()
    tide_times = [datetime.strptime(p['t'], "%Y-%m-%d %H:%M") for p in tide_data['predictions']]
    img_stream = plot_tide_chart(tide_data)
    forecast = fetch_7day_forecast()

    # Get today's weather details
    today_forecast = forecast[0]
    today_temperature = today_forecast['temperature']
    today_wind_speed = today_forecast['wind_speed']
    today_conditions = today_forecast['conditions']

    # Evaluate kayak conditions using tide data
    kayak_condition = evaluate_kayak_conditions(tide_times)

    # Compile the forecast table
    forecast_html = '<h3>7-Day Forecast</h3><table border="1"><tr><th>Date</th><th>Temperature (°F)</th><th>Wind Speed (knots)</th><th>Conditions</th><th>Kayak Condition</th></tr>'

    for day in forecast:
        date = datetime.fromisoformat(day['date']).strftime('%Y-%m-%d')
        temperature = day['temperature']
        wind_speed = day['wind_speed']
        conditions = day['conditions']

        # Evaluate kayak condition for each day based on tide data
        kayak_condition_day = evaluate_kayak_conditions(tide_times)

        forecast_html += f'<tr><td>{date}</td><td>{temperature}</td><td>{wind_speed}</td><td>{conditions}</td><td>{kayak_condition_day}</td></tr>'

    forecast_html += '</table>'

    # Email subject and body
    subject = "Today's Kayak Conditions and Tide Chart"
    body_text = f"""
    <html>
    <body>
        <h2>Kayak Conditions for Today</h2>
        <p>Tide-Based Kayak Condition: {kayak_condition}</p>
        <p>Temperature: {today_temperature}°F</p>
        <p>Wind Speed: {today_wind_speed} knots</p>
        <p>Weather Conditions: {today_conditions}</p>
        <h3>Tide Chart</h3>
        <img src="cid:tide_chart" alt="Tide Chart" />
        {forecast_html}
    </body>
    </html>
    """

    send_email(subject, body_text, img_stream)


if __name__ == "__main__":
    main()
