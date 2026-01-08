import arcade
import arcade.gui
import numpy as np
import threading
import time
from typing import Optional, Dict, List
from src.ui_components import (
    LapTimeLeaderboardComponent, 
    QualifyingSegmentSelectorComponent, 
    LegendComponent,
    build_track_from_example_lap
)
from src.f1_data import get_driver_quali_telemetry
from src.lib.time import format_time

FPS = 30
DT = 1 / FPS

class QualifyingReplay(arcade.Window):
    def __init__(self, session, data, title="Qualifying Results"):
        super().__init__(1280, 720, title, resizable=True)
        self.session = session
        self.data = data
        self.set_vsync(True)
        
        # UI State
        self.selected_driver = None
        self.loaded_telemetry = None  # Currently loaded telemetry data
        self.frames = []
        self.n_frames = 0
        self.play_time = 0.0
        self.paused = True
        self.playback_speed = 1.0
        self.loading_telemetry = False
        self.loading_message = ""
        
        # Store for comparison trace
        self.comparison_telemetry = None
        self.comparison_frames = []
        self.comparison_driver_code = None
        self.show_comparison = False

        # Chart state
        self.chart_active = False
        self.hover_x = None
        self.hover_y = None
        
        # Initialize UI Components
        self.leaderboard = LapTimeLeaderboardComponent(x=20)
        self.selector = QualifyingSegmentSelectorComponent()
        self.legend = LegendComponent(x=20, y=140)
        
        self.manager = arcade.gui.UIManager()
        self.manager.enable()

        # Build initial layout
        self.update_leaderboard()
        
        # Cached textures/data
        self.driver_colors = {}
        for res in self.data.get("results", []):
            code = res["code"]
            color = res.get("color", (255, 255, 255))
            if isinstance(color, list): color = tuple(color)
            self.driver_colors[code] = color
            
        # Track map data
        self.track_geom = None
        self.track_scale = 1.0
        self.track_offset_x = 0.0
        self.track_offset_y = 0.0
        self.track_bounds = None
        
        # Generate generic track geometry from the POLE SITTER or first result
        # We need a reference lap. 
        # Since we don't have the full session object readily available with laps unless passed,
        # we rely on 'data' which might have pre-fetched telemetry or we fetch it on demand.
        # But wait, we DO pass 'session' to __init__.
        try:
            # Pick pole position driver's fastest lap for map geometry
            pole_driver = session.results.iloc[0]["Abbreviation"]
            laps = session.laps.pick_drivers(pole_driver).pick_fastest()
            if not laps.empty:
                tel = laps.get_telemetry()
                self.track_geom = build_track_from_example_lap(tel)
                # Unpack bounds
                self.track_bounds = (
                    self.track_geom[6], self.track_geom[7], 
                    self.track_geom[8], self.track_geom[9]
                )
        except Exception as e:
            print(f"Could not build track map: {e}")
            self.track_geom = None

        # Pre-Load some telemetry for the pole sitter? No, let user select.
        
        # Setup Chart area
        self.chart_margins = {"left": 60, "right": 40, "top": 40, "bottom": 60}
        
        # Optimizations
        self._xs = None
        self._ys = None
        self._speeds = None
        self._times = None
        # Comparison arrays
        self._comp_xs = None
        self._comp_ys = None
        self._comp_speeds = None
        self._comp_times = None

        self.min_speed = 0.0
        self.max_speed = 350.0  # default range

    def update_leaderboard(self):
        results = self.data.get("results", [])
        entries = []
        for i, res in enumerate(results):
            # Sort keys: Q3 > Q2 > Q1
            # But the results list should already be sorted by position
            time_str = ""
            if res.get("Q3"): time_str = format_time(float(res["Q3"]))
            elif res.get("Q2"): time_str = format_time(float(res["Q2"]))
            elif res.get("Q1"): time_str = format_time(float(res["Q1"]))
            
            entries.append({
                "pos": res["position"],
                "code": res["code"],
                "color": res.get("color", (255,255,255)),
                "time": time_str
            })
        self.leaderboard.set_entries(entries)

    def on_resize(self, width, height):
        super().on_resize(width, height)
        # Update track scaling
        self.update_track_scaling(width, height)

    def update_track_scaling(self, width, height):
        if not self.track_geom: return
        
        # We want the track to be in the Top-Right quadrant or similar?
        # Actually design calls for:
        # Left: Leaderboard
        # Bottom: Chart
        # Center/Right: Track Map
        
        chart_height = 250
        track_area_x = 300
        track_area_y = chart_height + 20
        track_area_w = width - track_area_x - 20
        track_area_h = height - track_area_y - 20
        
        if track_area_w <= 0 or track_area_h <= 0: return
        
        x_min, x_max, y_min, y_max = self.track_bounds
        track_w = x_max - x_min
        track_h = y_max - y_min
        
        scale_w = track_area_w / track_w
        scale_h = track_area_h / track_h
        self.track_scale = min(scale_w, scale_h) * 0.90
        
        cx = (x_min + x_max) / 2
        cy = (y_min + y_max) / 2
        
        screen_cx = track_area_x + track_area_w / 2
        screen_cy = track_area_y + track_area_h / 2
        
        self.track_offset_x = screen_cx - cx * self.track_scale
        self.track_offset_y = screen_cy - cy * self.track_scale

    def world_to_screen(self, x, y):
        return (x * self.track_scale + self.track_offset_x, 
                y * self.track_scale + self.track_offset_y)

    def on_draw(self):
        self.clear()
        
        # Draw Leaderboard
        self.leaderboard.draw(self)
        
        # Draw Legend
        self.legend.draw(self)
        
        # Draw Track
        if self.track_geom:
            xi, yi = self.world_to_screen(self.track_geom[2], self.track_geom[3])
            xo, yo = self.world_to_screen(self.track_geom[4], self.track_geom[5])
            pts_i = list(zip(xi, yi))
            pts_o = list(zip(xo, yo))
            arcade.draw_line_strip(pts_i, arcade.color.GRAY, 2)
            arcade.draw_line_strip(pts_o, arcade.color.GRAY, 2)
        
        # Draw Selected Driver Dot on Track (if loaded)
        if self.frames and self.n_frames > 0:
            idx = int(self.frame_index)
            if idx < self.n_frames:
                frame = self.frames[idx]
                tel = frame.get("telemetry", {})
                tx, ty = tel.get("x"), tel.get("y")
                if tx is not None and ty is not None:
                    sx, sy = self.world_to_screen(tx, ty)
                    color = self.driver_colors.get(self.loaded_driver_code, arcade.color.RED)
                    arcade.draw_circle_filled(sx, sy, 8, color)
                    
        # Draw Comparison Driver Dot
        if self.show_comparison and self.comparison_frames:
            # We need to find the frame at current play_time
            # Comparison trace might define DIFFERENT time range.
            # Assuming play_time is relative to lap start (0.0), we can look it up.
            
            # Binary search for time
            if self._comp_times is not None:
                 idx_c = np.searchsorted(self._comp_times, self.play_time)
                 if idx_c < len(self._comp_times):
                     frame_c = self.comparison_frames[idx_c]
                     tel_c = frame_c.get("telemetry", {})
                     tx_c, ty_c = tel_c.get("x"), tel_c.get("y")
                     if tx_c is not None and ty_c is not None:
                         sx_c, sy_c = self.world_to_screen(tx_c, ty_c)
                         color_c = self.driver_colors.get(self.comparison_driver_code, arcade.color.CYAN) # Comparison is Cyan
                         arcade.draw_circle_filled(sx_c, sy_c, 6, color_c)

        # Draw Telemetry Chart (Speed / Throttle / Brake)
        if self.chart_active:
            self._draw_charts()
        
        # Draw Segment Selector (Modal)
        if self.selected_driver and not self.selector.selected_segment:
             # Only show if not already selected a segment to view? 
             # Logic: Clicking leaderboard sets selected_driver -> shows Modal -> Clicking segment -> loads telemetry -> closes modal
             self.selector.draw(self)

        # Loading overlay
        if self.loading_telemetry:
            arcade.draw_lrtb_rectangle_filled(0, self.width, self.height, 0, (0,0,0,150))
            arcade.Text(self.loading_message, self.width//2, self.height//2, 
                        arcade.color.WHITE, 20, anchor_x="center", anchor_y="center").draw()

        # Instructions
        if not self.selected_driver and not self.chart_active:
            arcade.Text("Select a driver from the leaderboard to view qualifying telemetry", 
                        self.width//2 + 100, self.height//2, arcade.color.GRAY, 16, anchor_x="center").draw()
            
    def _draw_charts(self):
        # Area for Speed Trace
        h = 200
        w = self.width - self.chart_margins["left"] - self.chart_margins["right"] - 300 # space for leaderboard
        x = 300 + self.chart_margins["left"] # shift right past leaderboard
        y = self.chart_margins["bottom"]
        
        # Background
        arcade.draw_lrtb_rectangle_filled(x, x+w, y+h, y, (20, 20, 20))
        arcade.draw_rect_outline(arcade.XYWH(x + w/2, y + h/2, w, h), arcade.color.DARK_GRAY, 1)

        if not self.frames: return

        # X-axis is Distance (normalized to total lap distance or just distance in meters)
        # Y-axis is Speed
        
        # Get data arrays
        dists = np.array([f["telemetry"]["dist"] for f in self.frames])
        speeds = self._speeds
        
        if dists.size == 0 or speeds is None: return
        
        max_dist = dists[-1]
        
        # Check comparison data
        comp_dists = None
        comp_speeds = None
        if self.show_comparison and self.comparison_frames:
             comp_dists = np.array([f["telemetry"]["dist"] for f in self.comparison_frames])
             comp_speeds = self._comp_speeds

        # Helper to map data to screen
        def map_pt(d, s):
            px = x + (d / max_dist) * w
            py = y + ((s - self.min_speed) / (self.max_speed - self.min_speed)) * h
            return px, py

        # Draw Main Trace
        points = []
        for i in range(len(dists)):
            points.append(map_pt(dists[i], speeds[i]))
        
        if points:
             arcade.draw_line_strip(points, arcade.color.YELLOW, 2)
        
        # Draw Comparison Trace
        if comp_dists is not None and comp_speeds is not None:
             c_points = []
             for i in range(len(comp_dists)):
                 # We assume comparison lap distance is roughly similar, scale it?
                 # Or just plot raw distance. If tracks match, distance should match.
                 # If valid lap.
                 c_points.append(map_pt(comp_dists[i], comp_speeds[i]))
             if c_points:
                 arcade.draw_line_strip(c_points, arcade.color.CYAN, 1) # thinner line

        # Draw Playhead
        current_frame = self.frames[min(int(self.frame_index), self.n_frames-1)]
        current_dist = current_frame["telemetry"]["dist"]
        px = x + (current_dist / max_dist) * w
        arcade.draw_line(px, y, px, y+h, arcade.color.WHITE, 1)
        
        # Display current values text
        info_x = x + 10
        info_y = y + h - 20
        spd = current_frame['telemetry']['speed']
        gear = current_frame['telemetry']['gear']
        drs_active = "ON" if current_frame['telemetry']['drs'] > 8 else "OFF"
        
        arcade.Text(f"{self.loaded_driver_code}: {spd:.0f} km/h  Gear: {gear}  DRS: {drs_active}",
                    info_x, info_y, arcade.color.YELLOW, 12).draw()

        if self.show_comparison and self.comparison_frames:
             # Find value at this distance?
             # Approximate
             idx_c = np.searchsorted(comp_dists, current_dist)
             if idx_c < len(comp_dists):
                 val_c = self.comparison_frames[idx_c]["telemetry"]["speed"]
                 delta = spd - val_c
                 delta_color = arcade.color.GREEN if delta > 0 else arcade.color.RED
                 arcade.Text(f"{self.comparison_driver_code}: {val_c:.0f} km/h (Delta: {delta:+.0f})",
                             info_x, info_y - 20, arcade.color.CYAN, 12).draw()
        
        
        # Inputs Trace (Throttle/Brake) - Smaller chart below? 
        # Or overlay? Overlay is messy.
        # Let's put throttle/brake bars on the side logic like in race replay?
        # Actually here we want to see trace over lap.
        # Let's draw separate small graphs below Speed chart
        
        h2 = 50
        y2 = y - h2 - 10
        
        # Throttle
        arcade.draw_lrtb_rectangle_filled(x, x+w, y2+h2, y2, (20, 20, 20))
        arcade.draw_rect_outline(arcade.XYWH(x + w/2, y2 + h2/2, w, h2), arcade.color.DARK_GRAY, 1)
        
        throttles = np.array([f["telemetry"]["throttle"] for f in self.frames])
        t_points = []
        for i in range(len(dists)):
            px = x + (dists[i] / max_dist) * w
            py = y2 + (throttles[i] / 100.0) * h2
            t_points.append((px, py))
        if t_points:
             arcade.draw_line_strip(t_points, arcade.color.GREEN, 1)
             
        # Brake
        brakes = np.array([f["telemetry"]["brake"] for f in self.frames])
        b_points = []
        for i in range(len(dists)):
            px = x + (dists[i] / max_dist) * w
            py = y2 + (brakes[i] / 100.0) * h2 # assuming brake 0-100 normalized
            b_points.append((px, py))
        if b_points:
             arcade.draw_line_strip(b_points, arcade.color.RED, 1)

    def on_mouse_press(self, x, y, button, modifiers):
        # Handle modal / components
        if self.selector.on_mouse_press(self, x, y, button, modifiers):
            return
        
        if self.leaderboard.on_mouse_press(self, x, y, button, modifiers):
            # new driver selected -> open segment selector
            if self.leaderboard.selected:
                self.selected_driver = self.leaderboard.selected
                # Reset previous loaded if different?
                # Actually we keep it until they click a segment
            return

        # Playback control via chart click?
        if self.chart_active:
             # Check bounds
             # Simplified: just check X
             if x > 360 and y < 300: # rough area
                 # seek
                 pass

    def on_key_press(self, symbol, modifiers):
        if symbol == arcade.key.SPACE:
            self.paused = not self.paused
        elif symbol == arcade.key.LEFT:
            self.play_time = max(self.play_start_t, self.play_time - 5.0)
        elif symbol == arcade.key.RIGHT:
             self.play_time = min(self.play_time + 5.0, float(self._times[-1]) if self._times is not None else 9999)
        elif symbol == arcade.key.UP:
             self.playback_speed *= 2
        elif symbol == arcade.key.DOWN:
             self.playback_speed /= 2
        elif symbol == arcade.key.C:
             # Toggle Comparison mode (Compare with Pole/P1)
             if not self.show_comparison:
                 self._load_comparison_telemetry()
             else:
                 self.show_comparison = False

    def _load_comparison_telemetry(self):
        # Load P1's Q3 telemetry (or same segment as current)
        if not self.loaded_telemetry: return
        
        # Determine target
        results = self.data.get("results", [])
        if not results: return
        
        # P1 is usually first
        target = results[0]["code"]
        if target == self.loaded_driver_code and len(results) > 1:
            target = results[1]["code"] # If we are P1, compare P2
            
        segment = self.loaded_driver_segment
        
        print(f"Loading comparison: {target} {segment}")
        self.comparison_driver_code = target
        
        # We need to fetch it in background potentially
        threading.Thread(target=self._bg_load_comp, args=(target, segment)).start()

    def _bg_load_comp(self, code, segment):
        try:
             # Try local cache
             telemetry = get_driver_quali_telemetry(self.session, code, segment)
             if telemetry:
                 frames = telemetry.get("frames", [])
                 self.comparison_frames = frames
                 # build arrays
                 times = [float(f.get("t")) for f in frames]
                 speeds = [f["telemetry"]["speed"] for f in frames]
                 self._comp_times = np.array(times)
                 self._comp_speeds = np.array(speeds)
                 self.show_comparison = True
        except Exception as e:
            print(f"Comparison load failed: {e}")

    def load_driver_telemetry(self, driver_code: str, segment_name: str):
        # This is called by the selector component
        print("Loading", driver_code, segment_name)
        
        # Reset state
        self.paused = True
        self.play_time = 0.0
        
        # Check if we already have it in self.data["telemetry"] (the big dump)
        telemetry = None
        if "telemetry" in self.data and driver_code in self.data["telemetry"]:
             drv_data = self.data["telemetry"][driver_code]
             if segment_name in drv_data:
                 telemetry = drv_data[segment_name]

        if telemetry and telemetry.get("frames"):
            # Instant load
            self.loaded_telemetry = telemetry
            self.loaded_driver_code = driver_code
            self.loaded_driver_segment = segment_name
            self.chart_active = True
            
            # Cache arrays
            frames = telemetry.get("frames", [])
            times = [float(f.get("t")) for f in frames if f.get("t") is not None]
            speeds = [ (f.get("telemetry") or {}).get("speed") for f in frames ]
            self._times = np.array(times) if times else None
            self._speeds = np.array([float(s) for s in speeds if s is not None]) if speeds else None
            self.frames = frames
            self.n_frames = len(frames)
            
            if self._speeds is not None and self._speeds.size > 0:
                self.min_speed = float(np.min(self._speeds))
                self.max_speed = float(np.max(self._speeds))
            else:
                self.min_speed = 0.0
                self.max_speed = 0.0
            
             # initialize playback state based on frames' timestamps
            frames = telemetry.get("frames", [])
            if frames:
                start_t = frames[0].get("t", 0.0)
                self.play_start_t = float(start_t)
                self.play_time = float(start_t)
                self.frame_index = 0
                self.paused = False
                self.playback_speed = 1.0
            self.loading_telemetry = False
            self.loading_message = ""
            return

        # Otherwise proceed with background loading as before
        self.loading_telemetry = True
        self.loading_message = f"Loading telemetry {driver_code} {segment_name}..."
        self.loaded_telemetry = None
        self.chart_active = False

        threading.Thread(
            target=self._bg_load_telemetry,
            args=(driver_code, segment_name),
            daemon=True
        ).start()

    def _bg_load_telemetry(self, driver_code: str, segment_name: str):
        """Background loader that fetches telemetry if not present locally."""
        try:
            telemetry = None
            # First double-check local store in background thread (race-safe)
            telemetry_store = self.data.get("telemetry") if isinstance(self.data, dict) else None
            if telemetry_store:
                driver_block = telemetry_store.get(driver_code) if isinstance(telemetry_store, dict) else None
                if driver_block:
                    seg = driver_block.get(segment_name)
                    if seg and isinstance(seg, dict) and seg.get("frames"):
                        telemetry = seg

            # If not found locally, attempt to fetch via API if a session is available
            if telemetry is None and getattr(self, "session", None) is not None:
                telemetry = get_driver_quali_telemetry(self.session, driver_code, segment_name)
            elif telemetry is None:
                # demo fallback: sleep briefly and leave telemetry None
                time.sleep(1.0)
                telemetry = None

            if telemetry is None:
                self.loaded_telemetry = None
                self.chart_active = False
            else:
                self.loaded_telemetry = telemetry
                self.loaded_driver_code = driver_code
                self.loaded_driver_segment = segment_name
                self.chart_active = True
                # cache arrays for fast indexing/interpolation
                frames = telemetry.get("frames", [])
                times = [float(f.get("t")) for f in frames if f.get("t") is not None]
                xs = [ (f.get("telemetry") or {}).get("x") for f in frames ]
                ys = [ (f.get("telemetry") or {}).get("y") for f in frames ]
                speeds = [ (f.get("telemetry") or {}).get("speed") for f in frames ]
                self._times = np.array(times) if times else None
                self._xs = np.array(xs) if xs else None
                self._ys = np.array(ys) if ys else None
                self._speeds = np.array([float(s) for s in speeds if s is not None]) if speeds else None
                self.frames = frames
                self.n_frames = len(frames)
                if self._speeds is not None and self._speeds.size > 0:
                    self.min_speed = float(np.min(self._speeds))
                    self.max_speed = float(np.max(self._speeds))
                else:
                    self.min_speed = 0.0
                    self.max_speed = 0.0
                # initialize playback state for the newly loaded telemetry
                frames = telemetry.get("frames", [])
                if frames:
                    start_t = frames[0].get("t", 0.0)
                    self.play_start_t = float(start_t)
                    self.play_time = float(start_t)
                    self.frame_index = 0
                    self.paused = False
                    self.playback_speed = 1.0
        except Exception as e:
            print("Telemetry load failed:", e)
            self.loaded_telemetry = None
            self.chart_active = False
        finally:
            self.loading_telemetry = False
            self.loading_message = ""

    def on_update(self, delta_time: float):
        # time-based playback synced to telemetry timestamps
        if not self.chart_active or self.loaded_telemetry is None:
            return
        if self.paused:
            return
        # advance play_time by delta_time scaled by playback_speed
        self.play_time += delta_time * self.playback_speed
        # compute integer frame index from cached times (fast, robust)
        if self._times is not None and len(self._times) > 0:
            # clamp play_time into available range
            clamped = min(max(self.play_time, float(self._times[0])), float(self._times[-1]))
            idx = int(np.searchsorted(self._times, clamped, side="right") - 1)
            self.frame_index = max(0, min(idx, len(self._times) - 1))
        else:
            # fallback: step frame index at FPS if no timestamps available
            self.frame_index = int(min(self.n_frames - 1, self.frame_index + int(round(delta_time * FPS * self.playback_speed))))

def run_qualifying_replay(session, data, title="Qualifying Results"):
    window = QualifyingReplay(session=session, data=data, title=title)
    arcade.run()
