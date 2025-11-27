import sys
import time
import subprocess
import math
import random
from pylogix import PLC

# Tags to emulate (Same as write_loop.py)
# Tags to emulate (Same as write_loop.py)
TAGS_DEF = [
    "M_0_0=DINT",
    "M_40_0=DINT",
    "M_0_11=DINT",
    "M_1_4=DINT",
    "M_1_5=DINT",
    "M_40_4=DINT",
    "W16_2=DINT",
    "W16_1=DINT",
    "B1_Bake_Time_ACC=REAL",
    "TMR_6_ACC=DINT",
    "B1_Bake_Time=REAL",  # Bake Timer Preset
    "M_3_0=DINT",         # Lights Status
    "M_1_0=DINT",         # Lights ON Command
    "M_0_15=DINT",        # Lights OFF Command
    "TMR_6_PRE=DINT",     # Cooldown Timer Preset
    "W00_15=DINT",        # Spray Temp Setpoint
    "W00_13=DINT",        # Bake Temp Setpoint
]

EMULATOR_IP = "127.0.0.1"

def start_emulator():
    cmd = [sys.executable, "-m", "cpppo.server.enip", "--address", "0.0.0.0:44818", *TAGS_DEF]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

def simulation_loop():
    print("Starting simulation loop...")
    with PLC() as comm:
        comm.IPAddress = EMULATOR_IP
        
        # Initialize some values if they are 0
        try:
            # Set initial setpoint if 0
            if comm.Read("W00_15").Value == 0:
                comm.Write("W00_15", 12000) # Spray SP default
            if comm.Read("W00_13").Value == 0:
                comm.Write("W00_13", 14000) # Bake SP default
                
            # Set initial bake time preset if 0
            if comm.Read("B1_Bake_Time").Value == 0:
                comm.Write("B1_Bake_Time", 30.0)
            # Set initial cooldown preset if 0
            if comm.Read("TMR_6_PRE").Value == 0:
                comm.Write("TMR_6_PRE", 300000) # 5 min
            # Set initial mode to Auto
            comm.Write("M_1_4", 1)
            comm.Write("M_1_5", 0)
        except Exception as e:
            print(f"Init error: {e}")

        start_time = time.time()
        
        while True:
            t = time.time() - start_time
            
            # Read current state for logic
            try:
                # Read commands and current states
                reads = comm.Read(["M_1_0", "M_0_15", "M_1_4", "M_1_5", "M_3_0", "M_0_11", "W00_15", "W00_13"])
                vals = {r.TagName: r.Value for r in reads if r.Status == "Success"}
                
                # Lights Logic
                # Latch M_3_0 based on commands
                if vals.get("M_1_0") == 1:
                    comm.Write("M_3_0", 1)
                    comm.Write("M_1_0", 0) # Reset command
                elif vals.get("M_0_15") == 1:
                    comm.Write("M_3_0", 0)
                    comm.Write("M_0_15", 0) # Reset command
                
                # Mode Logic: Ensure mutual exclusivity
                if vals.get("M_1_4") == 1 and vals.get("M_1_5") == 1:
                    comm.Write("M_1_5", 0) # Default to Auto
                elif vals.get("M_1_4") == 0 and vals.get("M_1_5") == 0:
                    comm.Write("M_1_4", 1) # Default to Auto
                
                # Setpoint Logic
                # Determine active setpoint based on mode (Auto = Bake Active)
                # If Bake Active (M_0_11), use W00_13 (Bake SP). Else use W00_15 (Spray SP).
                
                is_auto = vals.get("M_1_4", 1)
                bake_active = 1 if is_auto else 0
                
                # Update W16_1 based on state
                target_sp = vals.get("W00_13", 14000) if bake_active else vals.get("W00_15", 12000)
                comm.Write("W16_1", int(target_sp))
                
                # Simulate values
                # Temp: Sine wave between 70.0 and 150.0 degrees (scaled x100 -> 7000 to 15000)
                temp_val = 11000 + 4000 * math.sin(t * 0.5) 
                
                # Bake time ACC: Just incrementing minutes
                bake_time = (t / 60.0) % 60.0
                
                # Cooldown ACC: 5 minutes countdown (300000 ms)
                cooldown = 300000 - ((t * 1000) % 300000)
                
                # Bits
                system_on = 1
                heat_enabled = 1 if (int(t) % 10) < 8 else 0 # On for 8s, off for 2s
                
                comm.Write("M_0_0", system_on)
                comm.Write("M_40_0", heat_enabled)
                comm.Write("M_0_11", bake_active)
                comm.Write("W16_2", int(temp_val))
                comm.Write("B1_Bake_Time_ACC", float(bake_time))
                comm.Write("TMR_6_ACC", int(cooldown))
                comm.Write("M_40_4", 1) # Cooldown Active
                
            except Exception as e:
                print(f"Error in loop: {e}")
            
            time.sleep(0.2)

if __name__ == "__main__":
    # Start cpppo
    p = start_emulator()
    time.sleep(1)
    
    try:
        simulation_loop()
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        p.terminate()
