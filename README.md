# Paint Booth Dashboard

A web-based HMI dashboard for controlling and monitoring a paint booth system, built with Python (Flask) and interacting with Allen-Bradley CompactLogix PLCs via `pylogix`.

## Features
- **Real-time Monitoring**: Bake Timer, Temperature, System Status.
- **Controls**:
    - **Lights**: Toggle Booth Lights.
    - **Mode**: Switch between Auto (Restart Bake) and Manual (End Bake).
    - **Setpoints**: Adjust Spray Temperature and Bake Timer.
- **Responsive UI**: Designed for 10" HMI touchscreens with large buttons and dark mode.

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/davidjrb/paintbooth.git
    cd paintbooth
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Production
Run the application on the target HMI/Pi:
```bash
python3 paintbooth.py
```
*   **Port**: 5000
*   **PLC IP**: 192.168.1.1 (Configurable in `paintbooth.py`)

### Simulation / Demo
To run locally without a PLC:
1.  Edit `paintbooth.py` to set `PLC_IP = "127.0.0.1"`.
2.  Start the emulator:
    ```bash
    python3 run_demo.py
    ```
3.  Start the dashboard:
    ```bash
    python3 paintbooth.py
    ```

## File Structure
- `paintbooth.py`: Main Flask application.
- `run_demo.py`: PLC emulator using `cpppo`.
- `hmi_analysis_report.md`: Analysis of the original FactoryTalk View project.
