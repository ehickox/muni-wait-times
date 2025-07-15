#!/usr/bin/env python3
"""
SF Muni Live Transit Display for Raspberry Pi
Displays real-time arrival times for nearby stops
"""

import tkinter as tk
from tkinter import ttk
import requests
import json
import threading
import time
from datetime import datetime
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MuniDisplay:
    def __init__(self, root):
        self.root = root
        self.root.title("SF Muni Live Times")
        self.root.configure(bg='black')
        
        # Make fullscreen (optional - remove if you want windowed)
        #self.root.attributes('-fullscreen', True)
        self.root.bind('<Escape>', lambda e: self.root.quit())
        
        # API Configuration
        self.api_key = os.environ.get("511_API_KEY")  # Get from 511.org
        self.base_url = "http://api.511.org/transit/StopMonitoring"
        
        # Your stop configurations - replace with your actual stops
        self.stops = [
            {"code": "17874", "name": "Union Square Southbound", "routes": ["THIRD"]},
            {"code": "16524", "name": "Stockton St and Sutter St", "routes": ["STOCKTON", "UNION-STOCKTON"]},
            # Add more stops as needed
        ]
        self.destination_blacklist = ['4th St & Mission St']
        
        # Refresh interval (seconds)
        self.refresh_interval = 30
        
        # Create UI
        self.setup_ui()
        
        # Start data fetching
        self.update_data()
        
    def setup_ui(self):
        # Main container with gradient-like background
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)
        
        # Header section with SF Muni branding
        header_frame = tk.Frame(main_frame, bg='#1a1a1a')
        header_frame.pack(fill=tk.X, pady=(0, 30))
        
        # Title with SF Muni colors (red and white)
        title_label = tk.Label(
            header_frame,
            text="🚌 SF MUNI LIVE",
            font=('Helvetica', 40, 'bold'),
            fg='#E31837',  # SF Muni red
            bg='#1a1a1a',
            pady=10  # Added padding to prevent emoji clipping
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame,
            text="Real-time Arrivals to Caltrain Station",
            font=('Helvetica', 16),
            fg='#cccccc',
            bg='#1a1a1a'
        )
        subtitle_label.pack(pady=(5, 0))
        
        # Status bar
        status_frame = tk.Frame(main_frame, bg='#2d2d2d', relief=tk.RAISED, bd=1)
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        status_inner = tk.Frame(status_frame, bg='#2d2d2d')
        status_inner.pack(fill=tk.X, padx=15, pady=10)
        
        # Current time
        self.current_time_label = tk.Label(
            status_inner,
            text="",
            font=('Helvetica', 14, 'bold'),
            fg='#4CAF50',
            bg='#2d2d2d',
            padx=5, pady=5  # Added padding to prevent emoji clipping
        )
        self.current_time_label.pack(side=tk.LEFT)
        
        # Last updated
        self.last_updated_label = tk.Label(
            status_inner,
            text="🔄 Updating...",
            font=('Helvetica', 12),
            fg='#888888',
            bg='#2d2d2d',
            padx=5, pady=5  # Added padding to prevent emoji clipping
        )
        self.last_updated_label.pack(side=tk.RIGHT)
        
        # Stops container with horizontal layout
        stops_container = tk.Frame(main_frame, bg='#1a1a1a')
        stops_container.pack(fill=tk.BOTH, expand=True)
        
        # Create frames for each stop in a horizontal layout
        self.stop_frames = {}
        for i, stop in enumerate(self.stops):
            stop_frame = self.create_stop_frame(stops_container, stop)
            stop_frame.grid(row=0, column=i, padx=10, pady=5, sticky="nsew")
            stops_container.grid_columnconfigure(i, weight=1)
        
        # Update current time
        self.update_current_time()
    
    def create_stop_frame(self, parent, stop):
        """Create a stop frame with horizontal layout"""
        # Main stop container with modern card design
        stop_container = tk.Frame(parent, bg='#1a1a1a')
        
        # Stop card with rounded appearance (simulated with border)
        stop_frame = tk.Frame(stop_container, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        stop_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Stop header
        header_frame = tk.Frame(stop_frame, bg='#363636')
        header_frame.pack(fill=tk.X, padx=3, pady=3)
        
        # Stop icon and name
        header_content = tk.Frame(header_frame, bg='#363636')
        header_content.pack(fill=tk.X, padx=15, pady=12)
        
        # Stop icon with proper padding
        stop_icon = tk.Label(
            header_content,
            text="🚏",
            font=('Helvetica', 24),
            bg='#363636',
            padx=5, pady=5  # Added padding to prevent emoji clipping
        )
        stop_icon.pack(side=tk.LEFT, padx=(0, 10))
        
        # Stop name and details
        name_frame = tk.Frame(header_content, bg='#363636')
        name_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        name_label = tk.Label(
            name_frame,
            text=stop["name"],
            font=('Helvetica', 18, 'bold'),
            fg='#ffffff',
            bg='#363636',
            anchor='w',
            padx=5, pady=5  # Added padding to prevent text clipping
        )
        name_label.pack(anchor=tk.W)
        
        # Stop ID
        id_label = tk.Label(
            name_frame,
            text=f"Stop ID: {stop['code']}",
            font=('Helvetica', 11),
            fg='#888888',
            bg='#363636',
            anchor='w',
            padx=5  # Added padding to prevent text clipping
        )
        id_label.pack(anchor=tk.W)
        
        # Arrivals container
        arrivals_frame = tk.Frame(stop_frame, bg='#2d2d2d')
        arrivals_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=(0, 3))
        
        self.stop_frames[stop["code"]] = arrivals_frame
        
        return stop_container
    
    def fetch_stop_data(self, stop_code):
        """Fetch real-time data for a specific stop"""
        try:
            params = {
                'api_key': self.api_key,
                'agency': 'SF',  # SF Muni agency code
                'stopcode': stop_code,
                'format': 'json'
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            # Handle UTF-8 BOM by decoding with utf-8-sig
            text_content = response.content.decode('utf-8-sig')
            data = json.loads(text_content)
            
            return self.parse_arrival_data(data)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data for stop {stop_code}: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON for stop {stop_code}: {e}")
            logger.error(f"Response content (first 200 chars): {text_content[:200]}")
            return []
    
    def parse_arrival_data(self, data):
        """Parse the 511 API response to extract arrival times"""
        arrivals = []
        
        try:
            # Navigate the actual JSON structure based on the API response
            service_delivery = data.get('ServiceDelivery', {})
            stop_monitoring = service_delivery.get('StopMonitoringDelivery', {})
            
            # Get the MonitoredStopVisit array
            monitored_visits = stop_monitoring.get('MonitoredStopVisit', [])
            
            for visit in monitored_visits:
                journey = visit.get('MonitoredVehicleJourney', {})
                
                # Extract route info
                line_ref = journey.get('LineRef', '')
                route_name = journey.get('PublishedLineName', line_ref)
                
                # Extract arrival time from MonitoredCall
                monitored_call = journey.get('MonitoredCall', {})
                expected_arrival = monitored_call.get('ExpectedArrivalTime')
                
                # Also try AimedArrivalTime if ExpectedArrivalTime is not available
                if not expected_arrival:
                    expected_arrival = monitored_call.get('AimedArrivalTime')
                
                if expected_arrival:
                    try:
                        # Calculate minutes until arrival
                        arrival_time = datetime.fromisoformat(expected_arrival.replace('Z', '+00:00'))
                        now = datetime.now(arrival_time.tzinfo)
                        minutes_until = int((arrival_time - now).total_seconds() / 60)
                        
                        # Get destination
                        destination = journey.get('DestinationName', '')
                        if not destination:
                            destination = journey.get('DirectionRef', '')
                        
                        arrivals.append({
                            'route': route_name,
                            'minutes': max(0, minutes_until),  # Don't show negative times
                            'destination': destination,
                        })
                    except Exception as e:
                        logger.error(f"Error parsing arrival time {expected_arrival}: {e}")
                        continue
                
        except Exception as e:
            logger.error(f"Error parsing arrival data: {e}")
            logger.error(f"Data structure: {data}")
        
        return sorted(arrivals, key=lambda x: x['minutes'])
    
    def update_stop_display(self, stop_code, arrivals):
        """Update the display for a specific stop"""
        frame = self.stop_frames.get(stop_code)
        if not frame:
            return
        
        # Clear existing arrivals
        for widget in frame.winfo_children():
            widget.destroy()
        
        # Filter out arrivals less than 4 minutes
        filtered_arrivals = [arrival for arrival in arrivals if arrival['minutes'] >= 4]
        
        if not filtered_arrivals:
            no_data_container = tk.Frame(frame, bg='#2d2d2d')
            no_data_container.pack(fill=tk.X, padx=15, pady=15)
            
            no_data_label = tk.Label(
                no_data_container,
                text="⚠️ No upcoming arrivals (within 4+ min)",
                font=('Helvetica', 14),
                fg='#FFA726',
                bg='#2d2d2d',
                padx=5, pady=5
            )
            no_data_label.pack(anchor=tk.W)
            return
        
        # Display filtered arrivals
        for i, arrival in enumerate(filtered_arrivals[:6]):  # Show max 6 arrivals per stop
            arrival_container = tk.Frame(frame, bg='#2d2d2d')
            arrival_container.pack(fill=tk.X, padx=15, pady=8)
            
            # Route badge
            route_frame = tk.Frame(arrival_container, bg='#2d2d2d')
            route_frame.pack(side=tk.LEFT, padx=(0, 15))
            
            # Route number with colored background
            route_bg_color = self.get_route_color(arrival['route'])
            route_badge = tk.Label(
                route_frame,
                text=f" {arrival['route']} ",
                font=('Helvetica', 12, 'bold'),
                fg='white',
                bg=route_bg_color,
                relief=tk.RAISED,
                bd=1,
                padx=3, pady=3
            )
            route_badge.pack()
            
            # Arrival info
            info_frame = tk.Frame(arrival_container, bg='#2d2d2d')
            info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Time and destination
            time_icon, time_color = self.get_time_styling(arrival['minutes'])
            
            # Time display frame
            time_frame = tk.Frame(info_frame, bg='#2d2d2d')
            time_frame.pack(anchor=tk.W)
            
            # Colored dot emoji
            time_icon_label = tk.Label(
                time_frame,
                text=time_icon,
                font=('Segoe UI Emoji', 16),
                fg=time_color,
                bg='#2d2d2d',
                padx=0
            )
            time_icon_label.pack(side=tk.LEFT)
            
            # Minutes text
            time_text = f" {arrival['minutes']} min"
            if arrival['minutes'] == 1:
                time_text = " 1 min"
                
            time_label = tk.Label(
                time_frame,
                text=time_text,
                font=('Helvetica', 16, 'bold'),
                fg=time_color,
                bg='#2d2d2d',
                padx=0
            )
            time_label.pack(side=tk.LEFT)
            
            # Destination
            if arrival['destination']:
                dest_label = tk.Label(
                    info_frame,
                    text=f"→ {arrival['destination']}",
                    font=('Helvetica', 11),
                    fg='#cccccc',
                    bg='#2d2d2d',
                    anchor='w',
                    pady=2
                )
                dest_label.pack(anchor=tk.W)
            
            # Add separator line except for last item
            if i < len(filtered_arrivals[:6]) - 1:
                separator = tk.Frame(frame, height=1, bg='#404040')
                separator.pack(fill=tk.X, padx=15, pady=4)
    
    def get_route_color(self, route):
        """Get color for route badge based on route type"""
        route_lower = route.lower()
        if 'rapid' in route_lower or 'brt' in route_lower:
            return '#E31837'  # SF Muni red for rapid
        elif 'express' in route_lower:
            return '#1976D2'  # Blue for express
        elif route_lower.startswith('n'):
            return '#7B1FA2'  # Purple for night routes
        else:
            return '#388E3C'  # Green for regular routes
    
    def get_time_styling(self, minutes):
        """Get icon and color for arrival time. Assume it takes 11-12 minutes to get to station."""
        if minutes <= 9:
            return "🔴", "#FF1744"  # Red for now
        elif minutes <= 11:
            return "🟠", "#FF6D00"  # Orange for very soon
        elif minutes <= 12:
            return "🟡", "#FFD600"  # Yellow for soon
        elif minutes <= 13:
            return "🟢", "#4CAF50"  # Green for moderate
        else:
            return "🔵", "#2196F3"  # Blue for later
    
    def update_current_time(self):
        """Update the current time display"""
        current_time = datetime.now().strftime("%A, %B %d, %Y • %I:%M:%S %p")
        self.current_time_label.config(text=f"🕐 {current_time}")
        self.root.after(1000, self.update_current_time)
    
    def update_data(self):
        """Update all stop data"""
        def fetch_and_update():
            for stop in self.stops:
                arrivals = self.fetch_stop_data(stop["code"])
                # Filter out routes not specified:
                arrivals = [arrival for arrival in arrivals if arrival['route'] in stop["routes"] and arrival['destination'] not in self.destination_blacklist]
                self.root.after(0, self.update_stop_display, stop["code"], arrivals)
            
            # Update last updated timestamp
            current_time = datetime.now().strftime("%H:%M:%S")
            self.root.after(0, self.last_updated_label.config, 
                          {'text': f"🔄 Updated: {current_time}"})
        
        # Run in background thread to avoid blocking UI
        threading.Thread(target=fetch_and_update, daemon=True).start()
        
        # Schedule next update
        self.root.after(self.refresh_interval * 1000, self.update_data)

def main():
    root = tk.Tk()
    app = MuniDisplay(root)
    root.mainloop()

if __name__ == "__main__":
    main()