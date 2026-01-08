import arcade
from src.interfaces.race_replay import F1RaceReplayWindow

def run_arcade_replay(frames, track_statuses, example_lap, drivers, playback_speed=1.0, driver_colors=None, title="F1 Race Replay", total_laps=None, circuit_rotation=None, chart=False):
    window = F1RaceReplayWindow(
        frames=frames, 
        track_statuses=track_statuses,
        example_lap=example_lap, 
        drivers=drivers, 
        width=1280, 
        height=720, 
        title=title, 
        playback_speed=playback_speed,
        driver_colors=driver_colors,
        total_laps=total_laps,
        circuit_rotation=circuit_rotation,
        chart=chart,
    )
    arcade.run()
