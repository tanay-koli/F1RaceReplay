# F1 Race Replay

F1 Race Replay is a Python-based application that visualizes Formula 1 race telemetry data using the `fastf1` library and `arcade` game framework. It allows users to replay races, sprints, and qualifying sessions with a simplified 2D visualization.

## Features

- **Race Replay**: Watch a full replay of any F1 race.
- **Sprint & Qualifying Support**: Supports Sprint and Qualifying sessions.
- **Telemetry Data**: Uses real telemetry data fetched via `fastf1`.
- **Driver Info**: Displays driver names and colors.
- **Circuit Visualization**: Automatically generates circuit geometry based on telemetry.
- **Playback Speed**: Adjustable playback speed (though primarily set via code/args).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/tanay-koli/F1RaceReplay.git
    cd F1RaceReplay
    ```

2.  **Install dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    pip install -r requirements.txt
    ```

    *Dependencies:* `fastf1`, `pandas`, `matplotlib`, `numpy`, `arcade`, `pyglet`

## Usage

Run the application using `main.py` with command-line arguments to specify the session you want to view.

### Basic Usage

To watch the Race for the default season (2024) and round (1):

```bash
python main.py
```

### Command Line Arguments

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--year` | Season year (e.g., 2023, 2024) | 2024 |
| `--round` | Round number or name (e.g., 1, "Monaco") | 1 |
| `--sprint` | Load Sprint session instead of Race | False |
| `--qualifying` | Load Qualifying session | False |
| `--list-rounds` | List all rounds for the given year | False |
| `--list-sprints` | List all sprints for the given year | False |

### Examples

**Replay 2023 Monaco Grand Prix:**
```bash
python main.py --year 2023 --round "Monaco"
```

**Replay 2024 Round 5 Sprint:**
```bash
python main.py --year 2024 --round 5 --sprint
```

**View Qualifying for 2023 Round 1:**
```bash
python main.py --year 2023 --round 1 --qualifying
```

**List all rounds in 2024:**
```bash
python main.py --year 2024 --list-rounds
```

## Controls

*   (Note: Controls are currently handled by the application window logic. Closing the window ends the session.)

## License

[MIT License](LICENSE) (or applicable license - please check usage rights for FastF1 data)

## Acknowledgments

-   [FastF1](https://github.com/theOehrly/Fast-F1) for the amazing F1 data API.
-   [Python Arcade](https://api.arcade.academy/) for the 2D rendering engine.
