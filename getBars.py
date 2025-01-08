from flask import Flask, jsonify, request, render_template_string, url_for, send_from_directory
from flask_cors import CORS
import time
from datetime import datetime
import random

app = Flask(__name__)

########################Server

CORS(app)

def generate_base_minute_data(start_time, end_time):
    """Generate 1-minute base data"""
    data = []
    price = 40000
    
    current_time = start_time
    while current_time <= end_time:
        change_percent = random.uniform(-0.002, 0.002)
        price = price * (1 + change_percent)
        
        candle = {
            'time': current_time,
            'open': round(price * (1 + random.uniform(-0.001, 0.001)), 2),
            'high': round(price * (1 + random.uniform(0, 0.002)), 2),
            'low': round(price * (1 - random.uniform(0, 0.002)), 2),
            'close': round(price * (1 + random.uniform(-0.001, 0.001)), 2),
            'volumefrom': round(random.uniform(1, 10), 2)
        }
        candle['volumeto'] = candle['close'] * candle['volumefrom']
        data.append(candle)
        current_time += 60  # 1 minute increment
        
    return data

def aggregate_candles(minute_data, interval_minutes):
    """Aggregate 1-minute candles into larger timeframes"""
    if not minute_data:
        return []
    
    aggregated_data = []
    current_chunk = []
    
    for candle in minute_data:
        # Check if candle belongs to current chunk
        if not current_chunk or (candle['time'] - current_chunk[0]['time']) < interval_minutes * 60:
            current_chunk.append(candle)
        else:
            # Aggregate current chunk
            if current_chunk:
                aggregated_candle = {
                    'time': current_chunk[0]['time'],  # Use first candle's time
                    'open': current_chunk[0]['open'],  # First candle's open
                    'high': max(c['high'] for c in current_chunk),
                    'low': min(c['low'] for c in current_chunk),
                    'close': current_chunk[-1]['close'],  # Last candle's close
                    'volumefrom': sum(c['volumefrom'] for c in current_chunk),
                    'volumeto': sum(c['volumeto'] for c in current_chunk)
                }
                aggregated_data.append(aggregated_candle)
            current_chunk = [candle]
    
    # Don't forget the last chunk
    if current_chunk:
        aggregated_candle = {
            'time': current_chunk[0]['time'],
            'open': current_chunk[0]['open'],
            'high': max(c['high'] for c in current_chunk),
            'low': min(c['low'] for c in current_chunk),
            'close': current_chunk[-1]['close'],
            'volumefrom': sum(c['volumefrom'] for c in current_chunk),
            'volumeto': sum(c['volumeto'] for c in current_chunk)
        }
        aggregated_data.append(aggregated_candle)
    
    return aggregated_data

def get_data_for_resolution(resolution, to_ts=None, limit=2000):
    """Get data for any resolution using 1-minute data as base"""
    # Convert resolution to minutes
    if resolution.endswith('D'):
        interval_minutes = 1440  # Daily
    elif int(resolution) >= 60:
        interval_minutes = int(resolution)  # Hourly
    else:
        interval_minutes = int(resolution)  # Minutes
    
    # Calculate time range
    end_time = int(to_ts) if to_ts else int(time.time())
    # Need extra minutes to ensure we have enough data for aggregation
    start_time = end_time - (interval_minutes * 60 * limit)
    
    # Get base 1-minute data
    minute_data = generate_base_minute_data(start_time, end_time)
    
    # If requesting 1-minute data, return as is
    if interval_minutes == 1:
        data = minute_data
    else:
        # Aggregate to requested timeframe
        data = aggregate_candles(minute_data, interval_minutes)
    
    # Ensure we only return the requested number of candles
    data = data[-limit:] if len(data) > limit else data
    
    return {
        'Response': 'Success',
        'Data': data,
        'TimeTo': end_time,
        'TimeFrom': start_time,
        'FirstValueInArray': True,
        'ConversionType': {
            'type': 'direct',
            'conversionSymbol': ''
        }
    }

# All endpoints now use the same data generation function
@app.route('/data/histominute', methods=['GET'])
@app.route('/data/histohour', methods=['GET'])
@app.route('/data/histoday', methods=['GET'])
def get_history():
    limit = int(request.args.get('limit', 2000))
    to_ts = request.args.get('toTs')
    
    # Determine resolution based on endpoint
    if request.path == '/data/histoday':
        resolution = '1D'
    elif request.path == '/data/histohour':
        resolution = '60'
    else:
        resolution = '1'
    
    print(f"\nRequest - Path: {request.path}, Resolution: {resolution}, ToTs: {datetime.fromtimestamp(int(to_ts)) if to_ts else 'current'}")
    return jsonify(get_data_for_resolution(resolution, to_ts, limit))









###################Client

import os 

@app.route('/charting_library/<path:filename>')
def charting_library_files(filename):
    # Get the absolute path to the 'charting_library' folder
    charting_lib_path = os.path.join(app.root_path, 'charting_library')
    
    # Check if the requested file exists in the folder
    if os.path.exists(os.path.join(charting_lib_path, filename)):
        return send_from_directory(charting_lib_path, filename)
    else:
        return "File not found", 404

home_temp = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TradingView Charting Library - Local API</title>
  <script type="text/javascript" src="/charting_library/charting_library.standalone.js"></script>
  <style>
    #tv_chart_container {
      position: relative;
      height: 600px;
      width: 100%;
    }
  </style>
</head>
<body>
  <div id="tv_chart_container"></div>

  <script>
    const Datafeed = {
      onReady: function(callback) {
        setTimeout(() => {
          callback({
            supported_resolutions: ['1', '5', '15', '30', '60', '240', '1D'],
            supports_marks: false,
            supports_timescale_marks: false,
            supports_time: true
          });
        }, 0);
      },

      getBars: function(symbolInfo, resolution, periodParams, onHistoryCallback, onErrorCallback) {
        const { from, to, firstDataRequest } = periodParams;
        const apiRoot = 'http://localhost:5000';  // Changed to local Flask API
        const splitSymbol = symbolInfo.name.split(/[:/]/);
        
        const url = resolution.includes('D') ? '/data/histoday' : 
                   parseInt(resolution) >= 60 ? '/data/histohour' : '/data/histominute';
        
        const qs = {
          fsym: splitSymbol[1],
          tsym: splitSymbol[2],
          toTs: to,
          limit: 2000
        };

        const apiUrl = `${apiRoot}${url}?${new URLSearchParams(qs)}`;
        console.log('Fetching data from:', apiUrl);

        fetch(apiUrl)
          .then(response => response.json())
          .then(data => {
            if (data.Response === 'Error') {
              console.error('API Error:', data.Message);
              onErrorCallback(data.Message);
              return;
            }
            
            const bars = data.Data.map(el => ({
              time: el.time * 1000,
              low: el.low,
              high: el.high,
              open: el.open,
              close: el.close,
              volume: el.volumefrom
            }));

            console.log(`Received ${bars.length} bars for resolution ${resolution}`);
            onHistoryCallback(bars, { noData: !bars.length });
          })
          .catch(err => {
            console.error('Fetch Error:', err);
            onErrorCallback(err.message);
          });
      },

      resolveSymbol: function(symbolName, onSymbolResolvedCallback, onResolveErrorCallback) {
        setTimeout(() => {
          onSymbolResolvedCallback({
            name: symbolName,
            description: symbolName,
            type: 'crypto',
            session: '24x7',
            timezone: 'Etc/UTC',
            minmov: 1,
            pricescale: 100000,
            has_intraday: true,
            has_daily: true,
            supported_resolutions: ['1', '5', '15', '30', '60', '240', '1D']
          });
        }, 0);
      },

      // searchSymbols: function(userInput, exchange, symbolType, onResultReadyCallback) {
      //   onResultReadyCallback([]);
      // },

      subscribeBars: function(symbolInfo, resolution, onRealtimeCallback, subscriberUID, onResetCacheNeededCallback) {},
      unsubscribeBars: function(subscriberUID) {}
    };

    const widgetOptions = {
      symbol: 'Coinbase:BTC/USD',
      datafeed: Datafeed,
      interval: '15',
      container_id: 'tv_chart_container',
      library_path: '/charting_library/',
      locale: 'en',
      disabled_features: [
        'use_localstorage_for_settings',
        'study_templates'
      ],
      enabled_features: [],
      fullscreen: false,
      autosize: true,
      studies_overrides: {},
      overrides: {
        "paneProperties.background": "#131722",
        "paneProperties.vertGridProperties.color": "#363c4e",
        "paneProperties.horzGridProperties.color": "#363c4e",
        "symbolWatermarkProperties.transparency": 90,
        "scalesProperties.textColor": "#AAA",
        "mainSeriesProperties.candleStyle.wickUpColor": '#336854',
        "mainSeriesProperties.candleStyle.wickDownColor": '#7f323f'
      }
    };

    window.addEventListener('DOMContentLoaded', function() {
      if (typeof TradingView !== 'undefined') {
        const widget = new TradingView.widget(widgetOptions);
        widget.onChartReady(() => {
          console.log('Chart has loaded successfully!');
        });
      } else {
        console.error('TradingView library not found. Check the library_path configuration.');
      }
    });
  </script>
</body>
</html>
"""


@app.route('/')
def home():
    return render_template_string(home_temp) 






if __name__ == '__main__':
    app.run(debug=True, port=5000)