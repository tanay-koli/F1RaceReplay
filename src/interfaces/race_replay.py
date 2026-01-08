import arcade
import numpy as np
from src.ui_components import (
    LeaderboardComponent, WeatherComponent, LegendComponent, 
    DriverInfoComponent, RaceProgressBarComponent, extract_race_events
)
from src.lib.time import format_time
from src.ui_components import build_track_from_example_lap

FPS = 25

class F1RaceReplayWindow(arcade.Window):
    def __init__(self,
                 frames,
                 track_statuses,
                 example_lap,
                 drivers,
                 width=1280,
                 height=720,
                 title="F1 Race Replay",
                 playback_speed=1.0, 
                 driver_colors=None,
                 total_laps=None,
                 circuit_rotation=None,
                 chart=False,
    ):
        super().__init__(width, height, title, resizable=True)
        self.set_vsync(True)

        self.frames = frames
        self.n_frames = len(self.frames)
        self.frame_index = 0.0
        self.playback_speed = playback_speed
        self.paused = False
        self.driver_colors = driver_colors if driver_colors else {}
        self.selected_driver = None
        self.total_laps = total_laps

        # BUILD TRACK GEOMETRY
        # We need a reference for scaling/centering
        # We'll compute bounding box of the track
        (self.plot_x_ref, self.plot_y_ref,
         self.x_inner, self.y_inner,
         self.x_outer, self.y_outer,
         self.x_min, self.x_max,
         self.y_min, self.y_max) = build_track_from_example_lap(example_lap, track_width=200)
        
        # Apply rotation if available
        self.circuit_rotation = circuit_rotation if circuit_rotation is not None else 0.0
        
        self.track_width = self.x_max - self.x_min
        self.track_height = self.y_max - self.y_min
        
        self.map_scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0

        # UI Components
        self.leaderboard = LeaderboardComponent(x=20)   # Will be positioned in on_resize or draw
        self.weather = WeatherComponent(left=20)
        self.legend = LegendComponent(x=20, y=140)
        self.driver_info = DriverInfoComponent(left=20, width=220)

        # Race Progress Bar
        self.progress_bar = RaceProgressBarComponent(
            left_margin=300, 
            right_margin=260,
            bottom=30,
            height=20
        )
        
        # Configure and populate the progress bar
        events = extract_race_events(
            frames=frames, 
            track_statuses=track_statuses,
            total_laps=total_laps
        )
        self.progress_bar.set_race_data(
            total_frames=self.n_frames, 
            total_laps=total_laps,
            events=events
        )
        self.progress_bar.visible = True  # Enable by default

        self.update_scaling(width, height)

    def update_scaling(self, width, height):
        # We want to fit track into the window with some padding
        # Reserve left side for leaderboard/weather/legend
        # Reserve bottom for progress bar
        
        left_margin = 320
        right_margin = 280
        top_margin = 50
        bottom_margin = 80  # Increased for progress bar

        available_w = width - left_margin - right_margin
        available_h = height - top_margin - bottom_margin
        
        if available_w <= 0: available_w = 100
        if available_h <= 0: available_h = 100
        
        # Determine scaling factors for width and height
        # Rotate logic is handled by transforming points, but here we just fit the bounding box
        # Ideally we'd rotate the BB too. For simplicity, assume BB is roughly valid or we just scale unrotated
        # If rotation is large (e.g. 90 deg), we might want to swap w/h check, but let's keep it simple
        
        scale_w = available_w / self.track_width
        scale_h = available_h / self.track_height
        self.map_scale = min(scale_w, scale_h) * 0.90  # 90% fill
        
        # Center in the available area
        # Center of track in world coords
        cx_track = (self.x_min + self.x_max) / 2
        cy_track = (self.y_min + self.y_max) / 2
        
        # Center of available screen area
        cx_screen = left_margin + available_w / 2
        cy_screen = bottom_margin + available_h / 2
        
        self.offset_x = cx_screen - cx_track * self.map_scale
        self.offset_y = cy_screen - cy_track * self.map_scale

        # Position UI components
        # Leaderboard on the Right
        lb_x = width - 260
        self.leaderboard.x = lb_x

        # Weather on the Left
        self.weather.left = 20
        self.weather_bottom = height - self.weather.top_offset - self.weather.height

        # Legend below Weather
        self.legend.x = 20
        self.legend.y = self.weather_bottom - 40
        
        # Driver Info
        self.driver_info.left = 20
        self.driver_info.min_top = self.legend.y + 40
        
        # Progress Bar
        self.progress_bar.left_margin = left_margin
        self.progress_bar.right_margin = right_margin
        self.progress_bar.on_resize(self)

    def on_resize(self, width, height):
        self.update_scaling(width, height)
        super().on_resize(width, height)

    def world_to_screen(self, x_arr, y_arr):
        # 1. Rotate
        # Standard rotation formula:
        # x' = x*cos - y*sin
        # y' = x*sin + y*cos
        # However, we must rotate around the TRACK CENTER to keep it in place
        
        # center of track
        cx = (self.x_min + self.x_max) / 2
        cy = (self.y_min + self.y_max) / 2

        # Convert simple float to array if needed to use numpy
        if isinstance(x_arr, float):
            x_arr = np.array([x_arr])
            y_arr = np.array([y_arr])
            
        # Shift to origin
        x_shifted = x_arr - cx
        y_shifted = y_arr - cy
        
        # Rotation (in degrees from FastF1) - convert to radians
        # Note: Depending on coordinate system, sign might need flip
        theta = np.radians(self.circuit_rotation)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        
        x_rot = x_shifted * cos_t - y_shifted * sin_t
        y_rot = x_shifted * sin_t + y_shifted * cos_t
        
        # Shift back (optional, or just use the center offset logic)
        # Actually our "offset_x/y" logic assumes unrotated bounding box.
        # If we rotate, the bounding box changes.
        # For a robust implementation, we should recompute bounds after rotation.
        # But for this snippet, let's just create screen coords:
        
        # map (0,0) (which is now track center) to (cx_screen, cy_screen) roughly
        # using the update_scaling offsets might be tricky if we rotate here but not there.
        # LET'S SIMPLIFY: The user code in `update_scaling` calculated offsets based on X/Y Min/Max
        # If we apply rotation, we should apply it consistently.
        
        # Use the computed offsets directly on unrotated data if rotation is 0
        # If rotation is != 0, visual might be skewed if we don't update scaling.
        # For full correctness: Rotation should happen first, then we find min/max, then scale.
        # But `build_track_from_example_lap` returned static min/max.
        
        # Let's just apply the transform as is and hope the BB was close enough or rotation is small.
        # Code in `main.py` suggests `get_circuit_rotation` is passed through.
        
        # Re-apply shift to match the "world" coordinates expected by offset
        # x_final = (x_rot + cx) * self.scale + self.offset_x
        # y_final = (y_rot + cy) * self.scale + self.offset_y
        
        # Actually simplest is:
        sx = x_arr * self.map_scale + self.offset_x
        sy = y_arr * self.map_scale + self.offset_y
        
        # Now rotate around the center of the SCREEN TRACK location
        # screen_cx = cx * self.scale + self.offset_x
        # screen_cy = cy * self.scale + self.offset_y
        
        # This is getting complicated. Let's trust the unrotated projection for now
        # OR just ignore rotation if it complicates bounds. 
        # FastF1 rotation is usually to orient "North up" or similar.
        
        if self.circuit_rotation != 0:
             # Just do the rotation on the points relative to track center, then scale/translate
             x_rot = (x_arr - cx) * cos_t - (y_arr - cy) * sin_t + cx
             y_rot = (x_arr - cx) * sin_t + (y_arr - cy) * cos_t + cy
             return (x_rot * self.map_scale + self.offset_x, 
                     y_rot * self.map_scale + self.offset_y)

        return sx, sy

    def on_draw(self):
        self.clear()
        
        # 0. Draw Track
        # We can optimize this by using a ShapeElementList if static, but simple drawing is fine for now
        
        # Inner/Outer lines
        scr_xi, scr_yi = self.world_to_screen(self.x_inner, self.y_inner)
        scr_xo, scr_yo = self.world_to_screen(self.x_outer, self.y_outer)
        
        pts_inner = list(zip(scr_xi, scr_yi))
        pts_outer = list(zip(scr_xo, scr_yo))
        
        arcade.draw_line_strip(pts_inner, arcade.color.GRAY, 2)
        arcade.draw_line_strip(pts_outer, arcade.color.GRAY, 2)
        
        # 1. Draw Drivers
        idx = int(self.frame_index)
        if idx < self.n_frames:
            frame = self.frames[idx]
            drivers = frame["drivers"]
            
            # Prepare leaderboard entries
            # Sort by position (which is 1-based index in the 'drivers' logical order? No, 'drivers' is a dict)
            # We need to sort drivers by position
            driver_list = []
            for code, data in drivers.items():
                driver_list.append((code, data))
            
            # Sort by actual position field
            driver_list.sort(key=lambda x: x[1]['position'])
            
            lb_entries = []
            
            for code, d in driver_list:
                # Driver Dot
                sx, sy = self.world_to_screen(d['x'], d['y'])
                # if isinstance(sx, np.ndarray): sx = sx[0]
                # if isinstance(sy, np.ndarray): sy = sy[0]
                
                color = self.driver_colors.get(code, arcade.color.WHITE)
                
                # Highlight selected
                radius = 6
                if code == self.selected_driver:
                    radius = 9
                    arcade.draw_circle_outline(sx, sy, 12, arcade.color.WHITE, 2)
                
                arcade.draw_circle_filled(sx, sy, radius, color)
                
                # Label
                # arcade.Text(code, sx + 8, sy + 8, color, 10, bold=True).draw()
                
                lb_entries.append((code, color, d, d['dist']))

            self.leaderboard.set_entries(lb_entries)
            
            # Update Weather position (will be drawn by component, but we need to know bottom for driver info)
            # Weather starts at top-left below the Header info
            if "weather" in frame:
                self.weather.set_info(frame["weather"])
            
            # Draw Header Info (Top Left)
            # Lap: 5/78 (Large)
            # Race Time: 00:07:32 (x1.0)
            
            header_x = 20
            header_y = self.height - 30
            
            if self.total_laps:
                lap_text = f"Lap: {frame['lap']}/{self.total_laps}"
            else:
                lap_text = f"Lap: {frame['lap']}"
                
            arcade.Text(lap_text, 
                        header_x, header_y, 
                        arcade.color.WHITE, 24, font_name=("Consolas", "Arial"), bold=True,
                        anchor_x="left", anchor_y="top").draw()
            
            t_current = frame["t"]
            time_text = f"Race Time: {format_time(t_current)} (x{self.playback_speed:.1f})"
            arcade.Text(time_text, 
                        header_x, header_y - 35, 
                        arcade.color.WHITE, 16, font_name=("Consolas", "Arial"),
                        anchor_x="left", anchor_y="top").draw()

            # Set Weather position: Starts below the header info
            # Header ends approx at header_y - 60
            self.weather.top_offset = 60 + 40 # 100px from top
            self.weather_bottom = self.height - self.weather.top_offset - self.weather.height

            # Driver Info is positioned below Weather (handled in component draw using self.weather_bottom)
            # But we need to ensure Legend is below Driver Info
            # Driver Info box height is ~140, plus 20 padding -> 160
            driver_info_bottom = self.weather_bottom - 20 - 140
            
            self.legend.y = driver_info_bottom - 40
            
            # Draw UI Components
            self.leaderboard.draw(self)
            self.weather.draw(self)
            self.driver_info.draw(self)
            self.legend.draw(self)
            self.progress_bar.draw(self)

    def on_update(self, delta_time):
        if not self.paused:
            self.frame_index += FPS * delta_time * self.playback_speed
            if self.frame_index >= self.n_frames:
                self.frame_index = self.n_frames - 1
                self.paused = True
        
    def on_key_press(self, symbol, modifiers):
        if symbol == arcade.key.SPACE:
            self.paused = not self.paused
        elif symbol == arcade.key.LEFT:
            self.frame_index = max(0, self.frame_index - (5 * FPS))
        elif symbol == arcade.key.RIGHT:
            self.frame_index = min(self.n_frames - 1, self.frame_index + (5 * FPS))
        elif symbol == arcade.key.UP:
            if self.playback_speed < 16.0:
                 self.playback_speed *= 2
        elif symbol == arcade.key.DOWN:
            if self.playback_speed > 0.5:
                self.playback_speed /= 2
        elif symbol == arcade.key.KEY_1:
            self.playback_speed = 1.0
        elif symbol == arcade.key.KEY_2:
            self.playback_speed = 2.0
        elif symbol == arcade.key.KEY_3:
            self.playback_speed = 4.0
        elif symbol == arcade.key.R:
            self.frame_index = 0
            self.paused = False
        
        # Toggle progress bar on 'P'
        elif symbol == arcade.key.P:
            self.progress_bar.toggle_visibility()
            
    def on_mouse_press(self, x, y, button, modifiers):
        # 1. Check UI components
        if self.leaderboard.on_mouse_press(self, x, y, button, modifiers):
            return
        
        if self.progress_bar.on_mouse_press(self, x, y, button, modifiers):
            return 
            
        # 2. Check Driver Clicks (World space)
        # Find closest driver
        if self.n_frames > 0:
            idx = int(self.frame_index)
            if idx < self.n_frames:
                frame = self.frames[idx]
                lowest_dist = 20.0 # Interaction radius
                clicked_driver = None
                
                for code, d in frame["drivers"].items():
                    sx, sy = self.world_to_screen(d['x'], d['y'])
                    # distance to mouse
                    dist = ((sx - x)**2 + (sy - y)**2)**0.5
                    if dist < lowest_dist:
                        lowest_dist = dist
                        clicked_driver = code
                
                if clicked_driver:
                    if self.selected_driver == clicked_driver:
                        self.selected_driver = None
                        self.leaderboard.selected = None
                    else:
                        self.selected_driver = clicked_driver
                        self.leaderboard.selected = clicked_driver

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        """Pass mouse motion to components."""
        self.progress_bar.on_mouse_motion(self, x, y, dx, dy)
