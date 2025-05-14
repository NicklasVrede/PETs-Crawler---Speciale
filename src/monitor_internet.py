import time
import urllib.request
import threading
import platform
import subprocess
import datetime

def get_timestamp():
    """Return current time formatted as a string"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Determine which sound playing method to use based on platform
system = platform.system()

if system == "Windows":
    import winsound
    
    def play_alarm():
        """Play an alarm sound on Windows"""
        # Play Windows default beep sound (you can replace with a file)
        while not stop_alarm.is_set():
            winsound.Beep(1000, 500)  # 1000Hz for 500ms
            time.sleep(0.5)
            
else:  # For macOS and Linux
    def play_alarm():
        """Play an alarm sound on macOS/Linux"""
        while not stop_alarm.is_set():
            # Print '\a' (ASCII bell character) which makes a beep on most terminals
            print("\a", end="", flush=True)
            # You could also use subprocess to play a sound file:
            # subprocess.call(["afplay", "path/to/alarm.wav"])  # macOS
            # subprocess.call(["aplay", "path/to/alarm.wav"])   # Linux
            time.sleep(1)

# Flag to control alarm sound
stop_alarm = threading.Event()
alarm_thread = None

def check_internet():
    """Check if internet connection is available"""
    try:
        # Try multiple services with a shorter timeout
        for url in ['http://8.8.8.8', 'http://1.1.1.1', 'https://www.google.com']:
            try:
                urllib.request.urlopen(url, timeout=1)
                return True
            except:
                continue
        return False
    except:
        return False

def start_alarm():
    """Start the alarm in a separate thread"""
    global alarm_thread, stop_alarm
    
    # Reset the flag
    stop_alarm.clear()
    
    # Create and start a new thread if not already running
    if alarm_thread is None or not alarm_thread.is_alive():
        alarm_thread = threading.Thread(target=play_alarm)
        alarm_thread.daemon = True
        alarm_thread.start()

def stop_alarm_sound():
    """Stop the alarm sound"""
    global stop_alarm
    stop_alarm.set()

def main():
    print(f"[{get_timestamp()}] Internet connection monitor started...")
    print(f"[{get_timestamp()}] Press Ctrl+C to exit")
    
    # Track previous connection state - start as unknown
    was_connected = None
    
    try:
        while True:
            connected = check_internet()
            
            # First run - determine initial state without alarm
            if was_connected is None:
                was_connected = connected
                if not connected:
                    print(f"[{get_timestamp()}] Starting with no internet connection detected.")
                else:
                    print(f"[{get_timestamp()}] Internet connection detected.")
                continue
            
            # Connection lost
            if was_connected and not connected:
                print(f"[{get_timestamp()}] Internet connection LOST! Playing alarm...")
                start_alarm()
            
            # Connection restored
            elif not was_connected and connected:
                print(f"[{get_timestamp()}] Internet connection RESTORED! Stopping alarm...")
                stop_alarm_sound()
            
            # Update previous state
            was_connected = connected
            
            # Wait before checking again
            time.sleep(5)
            
    except KeyboardInterrupt:
        print(f"\n[{get_timestamp()}] Stopping internet connection monitor...")
        stop_alarm_sound()

if __name__ == "__main__":
    main()
