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
from datetime import datetime, timedelta
import logging
import os
import tkinter.font as tkfont

# Add this after your imports
def configure_fonts():
    default_font = tkfont.nametofont("TkDefaultFont")
    default_font.configure(family="DejaVu Sans", size=10)
    
    text_font = tkfont.nametofont("TkTextFont")
    text_font.configure(family="DejaVu Sans", size=10)
    
    fixed_font = tkfont.nametofont("TkFixedFont")
    fixed_font.configure(family="DejaVu Sans", size=10)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MuniDisplay:
    def __init__(self, root):
        self.root = root
        self.root.title("SF Muni Live Times")
        self.root.configure(bg='black')
        
        # Make fullscreen (optional - remove if you want windowed)
        self.root.attributes('-fullscreen', True)
        self.root.bind('<Escape>', lambda e: self.root.quit())
        
        # API Configuration
        self.api_key = os.environ.get("511_API_KEY")  # Get from 511.org
        self.base_url = "http://api.511.org/transit/StopMonitoring"
        
        # Your stop configurations - replace with your actual stops
        self.stops = [
            {"code": "17874", "name": "Union Square", "routes": ["THIRD"]},
            {"code": "16524", "name": "Stockton and Sutter", "routes": ["STOCKTON", "UNION-STOCKTON"]},
            {"code": "70012", "name": "Caltrain 4th & King", "routes": ["EXPRESS", "LIMITED", "LOCAL"], "agency": "CT"},  # Caltrain stop
        ]
        self.destination_blacklist = ['4th St & Mission St']
        
        # Refresh interval (seconds)
        self.refresh_interval = 62
        
        # Create UI
        self.setup_ui()
        
        # Start data fetching
        self.update_data()
        
        # Store next arrivals for commute calculation
        self.next_arrivals = {
            "17874": None,  # Union Square
            "16524": None,  # Stockton and Sutter
            "70012": None   # Caltrain
        }
        
    def setup_ui(self):
        # Main container with gradient-like background
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=15) 
        
        # Header section with SF Muni branding
        header_frame = tk.Frame(main_frame, bg='#1a1a1a')
        header_frame.pack(fill=tk.X, pady=(0, 30))
        
        # Title with SF Muni colors (red and white)
        title_label = tk.Label(
            header_frame,
            text="🚌 SF MUNI & CALTRAIN LIVE",
            font=('Helvetica', 35, 'bold'),
            fg='#E31837',  # SF Muni red
            bg='#1a1a1a',
            pady=10  # Added padding to prevent emoji clipping
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame,
            text="Real-time Arrivals to Caltrain Station",
            font=('Helvetica', 14),
            fg='#cccccc',
            bg='#1a1a1a'
        )
        subtitle_label.pack(pady=(5, 0))
        
        # Status bar
        status_frame = tk.Frame(main_frame, bg='#2d2d2d', relief=tk.RAISED, bd=1)
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        status_inner = tk.Frame(status_frame, bg='#2d2d2d')
        status_inner.pack(fill=tk.X, padx=15, pady=10)
        
        # Current time (shorter format to make room)
        self.current_time_label = tk.Label(
            status_inner,
            text="",
            font=('DejaVu Sans', 14, 'bold'),
            fg='#4CAF50',
            bg='#2d2d2d',
            padx=5, pady=5  # Added padding to prevent emoji clipping
        )
        self.current_time_label.pack(side=tk.LEFT)
        
        # Office arrival time - same size as date
        self.office_arrival_label = tk.Label(
            status_inner,
            text="🏢 Office: --:-- --",
            font=('DejaVu Sans', 14, 'bold'),
            fg='#2196F3',  # Default to blue
            bg='#2d2d2d',
            padx=5, pady=5
        )
        self.office_arrival_label.pack(side=tk.LEFT, expand=True, padx=(20, 0))
        
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
            stop_frame.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
            stops_container.grid_columnconfigure(i, weight=1, minsize=180)
        
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
        header_content.pack(fill=tk.X, padx=8, pady=6)  # Reduced from 15,12 
        
        # Stop icon with proper padding
        stop_icon = "🚆" if stop.get("agency") == "CT" else "🚏"
        stop_icon_label = tk.Label(
            header_content,
            text=stop_icon,
            font=('DejaVu Sans', 24),
            bg='#363636',
            padx=5, pady=5  # Added padding to prevent emoji clipping
        )
        stop_icon_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Stop name and details
        name_frame = tk.Frame(header_content, bg='#363636')
        name_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        name_label = tk.Label(
            name_frame,
            text=stop["name"],
            font=('Helvetica', 14, 'bold'),
            fg='#ffffff',
            bg='#363636',
            anchor='w',
            padx=5, pady=5  # Added padding to prevent text clipping
        )
        name_label.pack(anchor=tk.W)
        
        # Stop ID
        id_label = tk.Label(
            name_frame,
            text=f"ID: {stop['code']}",
            font=('Helvetica', 9),
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
    
    def fetch_stop_data(self, stop_code, agency="SF"):
        """Fetch real-time data for a specific stop"""
        try:
            params = {
                'api_key': self.api_key,
                'agency': agency,  # Default to SF Muni, can be overridden
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
        
        # Different filters for Caltrain vs Muni stops
        if stop_code == "70012":  # Caltrain stop
            filtered_arrivals = [arrival for arrival in arrivals if 25 <= arrival['minutes'] <= 60]
        else:  # Muni stops
            filtered_arrivals = [arrival for arrival in arrivals if arrival['minutes'] >= 4] 
        
        # Store next arrival for commute calculation
        if stop_code in self.next_arrivals:
            self.next_arrivals[stop_code] = filtered_arrivals[0]['minutes'] if filtered_arrivals else None
        
        # Update office arrival estimate
        self.update_office_arrival()
        
        if not filtered_arrivals:
            no_data_container = tk.Frame(frame, bg='#2d2d2d')
            no_data_container.pack(fill=tk.X, padx=15, pady=15)
            
            no_data_text = "⚠️ No upcoming arrivals (within 25-60 min)" if stop_code == "70012" else "⚠️ No upcoming arrivals (within 4+ min)"
            no_data_label = tk.Label(
                no_data_container,
                text=no_data_text,
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
            arrival_container.pack(fill=tk.X, padx=8, pady=4)
            
            # Route badge
            route_frame = tk.Frame(arrival_container, bg='#2d2d2d')
            route_frame.pack(side=tk.LEFT, padx=(0, 15))
            
            # Route number with colored background
            route_bg_color = self.get_route_color(arrival['route'])
            route_badge = tk.Label(
                route_frame,
                text=f"{arrival['route']}",
                font=('Helvetica', 10, 'bold'),
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
                font=('DejaVu Sans', 16),
                fg=time_color,
                bg='#2d2d2d',
                padx=0
            )
            time_icon_label.pack(side=tk.LEFT)
            
                
            time_label = tk.Label(
                time_frame,
                text=f"{arrival['minutes']}m",
                font=('Helvetica', 12, 'bold'),
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
                    font=('Helvetica', 9),
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
    
    def update_office_arrival(self):
        """Calculate and display estimated arrival time at office with color coding"""
        try:
            # Get next arrivals for relevant stops
            union_arrival = self.next_arrivals["17874"]
            stockton_arrival = self.next_arrivals["16524"]
            caltrain_arrival = self.next_arrivals["70012"]
            
            # If we don't have all required data
            if None in [union_arrival, stockton_arrival, caltrain_arrival]:
                self.office_arrival_label.config(text="🏢 Office: Calculating...", fg='#2196F3')
                return
            
            # Calculate commute times
            muni_time = min(union_arrival + 15, stockton_arrival + 10)  # Muni travel time to Caltrain
            caltrain_time = caltrain_arrival + 49  # Caltrain to Palo Alto worst case local train
            walk_time = 7  # Walk from Palo Alto station to office
            
            # Total commute time in minutes
            total_commute = 13 + muni_time + caltrain_time + walk_time
            
            # Calculate arrival time
            arrival_time = datetime.now() + timedelta(minutes=total_commute)
            arrival_str = arrival_time.strftime("%I:%M %p")
            
            # Set color based on arrival time
            arrival_hour = arrival_time.hour
            arrival_minute = arrival_time.minute
            
            # Determine color and emoji
            if arrival_hour < 8 or (arrival_hour == 8 and arrival_minute < 30):
                # Before 8:30am - blue
                color = '#2196F3'
                emoji = "🏢"
            elif arrival_hour == 8 and arrival_minute < 56:
                # Between 8:30-8:56am - orange
                color = '#FF9800'
                emoji = "🏢"
            else:
                # After 8:56am - red with alarm
                color = '#F44336'
                emoji = "⏰"
            
            self.office_arrival_label.config(
                text=f"{emoji} Office: {arrival_str}",
                fg=color
            )
        except Exception as e:
            logger.error(f"Error calculating office arrival: {e}")
            self.office_arrival_label.config(text="🏢 Office: Error", fg='#F44336')
    
    def get_route_color(self, route):
        """Get color for route badge based on route type"""
        route_lower = route.lower()
        if 'rapid' in route_lower or 'brt' in route_lower:
            return '#E31837'  # SF Muni red for rapid
        elif 'express' in route_lower:
            return '#1976D2'  # Blue for express
        elif 'limited' in route_lower:
            return '#7B1FA2'  # Purple for limited/express
        elif route_lower.startswith('n'):
            return '#7B1FA2'  # Purple for night routes
        elif 'local' in route_lower:
            return '#388E3C'  # Green for regular routes
        else:
            return '#FF9800'  # Orange for other routes
    
    def get_time_styling(self, minutes):
        """Get icon and color for arrival time. Assume it takes 11-12 minutes to get to station."""
        if minutes <= 9:
            return "●", "#FF1744"  # Red circle
        elif minutes <= 11:
            return "●", "#FF6D00"  # Orange circle
        elif minutes <= 12:
            return "●", "#FFD600"  # Yellow circle
        elif minutes <= 13:
            return "●", "#4CAF50"  # Green circle
        else:
            return "●", "#2196F3"  # Blue circle 
    
    def update_current_time(self):
        """Update the current time display"""
        current_time = datetime.now().strftime("%a %b %d • %I:%M %p")  # Shorter format
        self.current_time_label.config(text=f"🕐 {current_time}")
        self.root.after(1000, self.update_current_time)
    
    def update_data(self):
        """Update all stop data"""
        def fetch_and_update():
            for stop in self.stops:
                agency = stop.get("agency", "SF")  # Default to SF Muni if not specified
                arrivals = self.fetch_stop_data(stop["code"], agency)
                # Filter out routes not specified:
                print(arrivals)
                if agency == 'SF':
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
    # Call this function before creating your main window
    configure_fonts()
    root.mainloop()

if __name__ == "__main__":
    main()