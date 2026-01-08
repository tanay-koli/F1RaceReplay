import sys
import argparse
import fastf1
from src.f1_data import (
    get_race_telemetry, 
    enable_cache, 
    get_circuit_rotation, 
    load_session, 
    get_quali_telemetry,
    list_rounds,
    list_sprints
)
from src.arcade_replay import run_arcade_replay
from src.interfaces.qualifying import run_qualifying_replay

def main(year=None, round_number=None, playback_speed=1, session_type='R'):
  print(f"Loading F1 {year} Round {round_number} Session '{session_type}'")
  session = load_session(year, round_number, session_type)

  print(f"Loaded session: {session.event['EventName']} - {session.event['RoundNumber']} - {session_type}")

  # Enable cache for fastf1
  enable_cache()

  if session_type == 'Q' or session_type == 'SQ':
    qualifying_session_data = get_quali_telemetry(session, session_type=session_type)
    title = f"{session.event['EventName']} - {'Sprint Qualifying' if session_type == 'SQ' else 'Qualifying Results'}"
    run_qualifying_replay(
      session=session,
      data=qualifying_session_data,
      title=title,
    )
  else:
    race_telemetry = get_race_telemetry(session, session_type=session_type)
    example_lap = session.laps.pick_fastest().get_telemetry()
    drivers = session.drivers
    
    circuit_rotation = get_circuit_rotation(session)
    chart = "--chart" in sys.argv

    run_arcade_replay(
        frames=race_telemetry['frames'],
        track_statuses=race_telemetry['track_statuses'],
        example_lap=example_lap,
        drivers=drivers,
        playback_speed=1.0,
        driver_colors=race_telemetry['driver_colors'],
        title=f"{session.event['EventName']} - {'Sprint' if session_type == 'S' else 'Race'}",
        total_laps=race_telemetry['total_laps'],
        circuit_rotation=circuit_rotation,
        chart=chart,
    )

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="F1 Race Replay")
  parser.add_argument("--year", type=int, default=2024, help="Season year") # Update to 2024 as default for relevance? Source used 2025. I'll stick to 2025 if source had it, or 2024. Source used 2025 in README but might be hypothetical.
  # Source README said `python main.py --year 2025 --round 12`. I'll use 2024 as default to be safe or 2023. Let's use 2023 as default as 2025 hasn't happened.
  # Actually, the source code viewed in Step 88 said "loading F1 2025". I'll default to 2023 for safety as it has data.
  parser.add_argument("--round", type=str, default="1", help="Round number or name")
  parser.add_argument("--sprint", action="store_true", help="Load Sprint session")
  parser.add_argument("--qualifying", action="store_true", help="Load Qualifying session")
  parser.add_argument("--refresh-data", action="store_true", help="Recompute telemetry")
  parser.add_argument("--chart", action="store_true", help="Show chart (Race only, deprecated)")
  parser.add_argument("--list-rounds", action="store_true", help="List all rounds for the given year")
  parser.add_argument("--list-sprints", action="store_true", help="List all sprints for the given year")
  
  args = parser.parse_args()

  if args.list_rounds:
      list_rounds(args.year)
      sys.exit()

  if args.list_sprints:
      list_sprints(args.year)
      sys.exit()

  session_type = 'R'
  if args.sprint and args.qualifying:
      session_type = 'SQ'
  elif args.sprint:
      session_type = 'S'
  elif args.qualifying:
      session_type = 'Q'

  main(year=args.year, round_number=args.round, session_type=session_type)
