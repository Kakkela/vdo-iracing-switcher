import irsdk
import time
import requests
import sys
from dataclasses import dataclass
from typing import Dict, Optional

# Constants
SLEEP_INTERVAL = 1  # seconds
NO_SCENE_ID = -1
VDO_API_URL = 'https://api.vdo.ninja'


@dataclass
class AppState:
    """Application state container."""
    ir_connected: bool = False
    vdo_current_scene_id: int = NO_SCENE_ID
    vdo_api_key: str = ""
    last_displayed_driver_id: int = NO_SCENE_ID


class iRacingSwitcher:
    """Main application class for iRacing to VDO.NINJA integration."""
    
    def __init__(self):
        self.ir = irsdk.IRSDK()
        self.state = AppState()
    
    def request_api_key(self, api_key: Optional[str] = None) -> None:
        """Prompt user for VDO.NINJA API key, or use provided one.
        
        Args:
            api_key: Optional API key to use. If not provided, prompt user.
        """
        if api_key:
            self.state.vdo_api_key = api_key.strip()
        else:
            self.state.vdo_api_key = input("Enter API.VDO.NINJA key: ").strip()
        
        if not self.state.vdo_api_key:
            raise ValueError("API key cannot be empty")
        
        print(f"API Key: {self.state.vdo_api_key}")
    
    def check_iracing_connection(self) -> None:
        """Check and update iRacing connection status."""
        is_connected = self.ir.is_initialized and self.ir.is_connected
        
        if self.state.ir_connected and not is_connected:
            self.state.ir_connected = False
            self.ir.shutdown()
            print('iRacing connection lost')
        elif not self.state.ir_connected and self.ir.startup() and is_connected:
            self.state.ir_connected = True
            print('iRacing connected')
    
    def switch_vdo_scene(self, old_scene_id: int, new_scene_id: int) -> bool:
        """
        Switch VDO.NINJA scene.
        
        Args:
            old_scene_id: Current scene ID to disable
            new_scene_id: New scene ID to enable
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{VDO_API_URL}/{self.state.vdo_api_key}/"
            
            # Disable old scene if valid
            if old_scene_id != NO_SCENE_ID:
                payload = {"action": "addScene", "target": str(old_scene_id), "value": 1}
                response = requests.post(url, json=payload, timeout=5)
                response.raise_for_status()
            
            # Enable new scene
            payload = {"action": "addScene", "target": str(new_scene_id), "value": 1}
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            
            return True
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return False
    
    def process_telemetry(self) -> None:
        """Process iRacing telemetry and update VDO scene accordingly."""
        try:
            self.ir.freeze_var_buffer_latest()
            
            # Get driver info
            driver_info = self.ir['DriverInfo']['Drivers']
            if not driver_info:
                return
            
            # Build CarIdx to UserID and UserName mappings
            caridx_to_userid = {d['CarIdx']: d['UserID'] for d in driver_info}
            caridx_to_username = {d['CarIdx']: d['UserName'] for d in driver_info}
            
            # Get current camera car ID
            cam_car_idx = self.ir['CamCarIdx']
            current_id = caridx_to_userid.get(cam_car_idx)
            current_name = caridx_to_username.get(cam_car_idx)
            
            if current_id is None:
                return
            
            # Display focused driver ID and name if changed
            if self.state.last_displayed_driver_id != current_id:
                display_text = f"Focused Driver ID: {current_id} | Name: {current_name}"
                # Pad with spaces to clear any remaining characters from previous longer text
                print(f"\r{display_text:<80}", end='', flush=True)
                self.state.last_displayed_driver_id = current_id
            
            # Switch scene if camera changed
            if self.state.vdo_current_scene_id != current_id:
                # On first run, sync to current state without API call
                if self.state.vdo_current_scene_id == NO_SCENE_ID:
                    self.state.vdo_current_scene_id = current_id
                elif self.switch_vdo_scene(self.state.vdo_current_scene_id, current_id):
                    self.state.vdo_current_scene_id = current_id
        
        except (KeyError, IndexError) as e:
            print(f"Telemetry processing error: {e}")
    
    def run(self) -> None:
        """Main application loop."""
        try:
            while True:
                self.check_iracing_connection()
                if self.state.ir_connected:
                    self.process_telemetry()
                time.sleep(SLEEP_INTERVAL)
        except KeyboardInterrupt:
            print("\nShutting down...")
            if self.state.ir_connected:
                self.ir.shutdown()


if __name__ == '__main__':
    # Parse command-line arguments
    api_key = None
    if '--api-key' in sys.argv:
        idx = sys.argv.index('--api-key')
        if idx + 1 < len(sys.argv):
            api_key = sys.argv[idx + 1]
    
    app = iRacingSwitcher()
    app.request_api_key(api_key)
    app.run()
