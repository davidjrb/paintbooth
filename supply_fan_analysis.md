# Supply Fan Logic Analysis (vD L5X)

Based on the analysis of `MainProgram_Program_vD.L5X`, here is the exact logic controlling the Supply Fan and the potential reasons for it not starting, with specific **Rung Numbers** for troubleshooting.

## 1. Supply Fan Output Tag
The Supply Fan is controlled by **`M[3].4`** (Supply Fan Starter 1).
*   **Logic Location**: **Rung 92**
*   **Logic**: `XIC(M[2].0) XIC(M[0].0) XIC(M[0].3) OTE(M[3].4)`
*   **Requirements to Run**:
    1.  **`M[2].0`** (Rung 11): Center Door Closed.
    2.  **`M[0].0`** (Rung 86): System ON.
    3.  **`M[0].3`** (Rung 42): Exhaust Fan 1 Air Proving Good.

## 2. The Start Sequence & Dependencies
The Supply Fan is the *last* step in the startup chain. It will not start until the Exhaust Fan has proven airflow.

### Step 1: System ON (`M[0].0`)
*   **Logic Location**: **Rung 86**
*   **Inhibits**: If **`M[0].8`** (Rung 116) is True, the System turns OFF immediately.
    *   **Rung 116** shows that `M[0].8` is triggered if **Manual Mode** (`M[1].5`) is active (and cooldown is done). This confirms why the "Both High" Auto/Manual buttons killed the system.
*   **Faults**: Requires `R000.0` (Overload) and `R000.11` (Flame Fail) to be OK (Rung 86).

### Step 2: Damper Open (`M[3].2`)
*   **Logic Location**: **Rung 89**
*   Turns ON immediately with System ON (`M[0].0`).
*   **Physical Check**: Verify the intake damper is actually opening.

### Step 3: Exhaust Fan Start (`M[3].3`)
*   **Logic Location**: **Rung 91**
*   **Logic**: Starts if Damper End Switch **`R000.8`** closes *during* the Startup Timer **`TMR[4]`** window.
*   **Critical Timing**: If the Damper takes too long to open (longer than `TMR[4]` preset), the Exhaust Fan will NOT start.
*   **Tag to Check**: `R000.8` (Damper End Switch Input) at **Rung 91**.

### Step 4: Exhaust Proving (`M[0].3`)
*   **Logic Location**: **Rung 42**
*   **Logic**: Driven by **`TMR[0]`** Done bit.
*   **Timer Logic**: **Rung 41** starts `TMR[0]` when Exhaust Fan Output **`R003.0`** is ON and Exhaust Proving Switch **`R000.1`** is Closed.
*   **Tag to Check**: `R000.1` (Exhaust Proving Switch Input) at **Rung 41**.
*   **Failure Mode**: If the Exhaust Fan runs but `R000.1` doesn't close (broken belt, bad switch, blocked filter), `M[0].3` will never turn on, and the Supply Fan (Rung 92) will never start.

## Summary of Checks
If the Supply Fan is not starting, check these tags in this order:
1.  **`M[0].0`** (Rung 86): Is the System ON? (If not, check `M[0].8` at Rung 116).
2.  **`R000.8`** (Rung 91): Is the Damper End Switch closing?
3.  **`M[3].3`** (Rung 91): Is the Exhaust Fan running?
4.  **`R000.1`** (Rung 41): Is the Exhaust Proving Switch closing?
