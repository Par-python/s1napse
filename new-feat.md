# S1napse — Live Math Channels: Implementation Prompt

> **Purpose:** This document is a detailed engineering prompt for Claude Code to implement a live math channel system for the S1napse telemetry app. Read this entire document before writing any code.

## 1. What This Feature Does

The user writes a formula like:

```
front_brake_bias = brake_temp_fl / (brake_temp_fl + brake_temp_rl) * 100
```

And it becomes a live channel at the telemetry tick rate. It appears in the graph channel selector, can be plotted alongside real channels, updates every tick, persists across sessions, and exports with everything else.

**Two audiences:**

- **Beginners** never touch this directly. They benefit from pre-built math channels that ship with the app (tyre balance indicators, trail braking flag, throttle smoothness). These appear as ready-made channels in the graph selector.
- **Experts** open the Math Channel Manager, write their own formulas, chain channels together, and use it as a live analysis workbench — the same workflow MoTeC i2 offers, inside S1napse.

---

## 2. Formula Engine

### 2.1 — Parser

Use Python's `ast` module to parse formula strings into an abstract syntax tree. Walk the tree to evaluate. This is safe (no arbitrary code execution) and fast enough for real-time evaluation.

**Do NOT use `eval()`, `exec()`, or `compile()` with code execution.** Only `ast.parse()` with a strict AST node whitelist.

**Allowed AST nodes:**

```python
ALLOWED_NODES = {
    ast.Expression,
    ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp, ast.IfExp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
    ast.USub, ast.UAdd, ast.Not,
    ast.Gt, ast.Lt, ast.GtE, ast.LtE, ast.Eq, ast.NotEq,
    ast.And, ast.Or,
    ast.Call, ast.Name, ast.Constant,
    ast.Load,  # needed for Name nodes
}
```

Any AST node NOT in this set should raise a validation error. This blocks attribute access, imports, subscripts, assignments, lambdas, comprehensions, and everything else that could be dangerous.

### 2.2 — Variable resolution

Any `ast.Name` node in the formula is resolved in this order:

1. **Constants:** `pi`, `e` (math constants)
2. **Special variables:** `dt` (time delta between current and previous sample, in seconds)
3. **Raw telemetry channels:** match against the current telemetry channel names (e.g., `speed`, `brake`, `tyre_temp_fl_i`)
4. **Other math channels:** match against user-defined and built-in math channel names
5. **No match:** raise a validation error with message `"Unknown channel: '{name}'. Available channels: {list}"`

### 2.3 — Built-in functions

These are the only callable functions allowed in formulas. Any `ast.Call` node whose function name is not in this table should raise a validation error.

| Function                        | Args | Description                              | Implementation                              |
| ------------------------------- | ---- | ---------------------------------------- | ------------------------------------------- |
| `abs(x)`                        | 1    | Absolute value                           | `builtins.abs()`                            |
| `min(a, b)`                     | 2    | Minimum of two values                    | `builtins.min()`                            |
| `max(a, b)`                     | 2    | Maximum of two values                    | `builtins.max()`                            |
| `sqrt(x)`                       | 1    | Square root                              | `math.sqrt()`, return 0.0 if x < 0          |
| `avg(a, b, ...)`                | 2+   | Mean of N values                         | `sum(args) / len(args)`                     |
| `clamp(x, lo, hi)`              | 3    | Clamp value to range                     | `max(lo, min(hi, x))`                       |
| `prev(channel)`                 | 1    | Previous sample value of a channel       | See §3.4                                    |
| `prev(channel, n)`              | 2    | Value N samples ago                      | See §3.4                                    |
| `delta(channel)`                | 1    | `channel - prev(channel)`                | See §3.4                                    |
| `rate(channel)`                 | 1    | `delta(channel) / dt`                    | See §3.4                                    |
| `rolling_avg(channel, n)`       | 2    | Moving average over last N samples       | See §3.4                                    |
| `rolling_max(channel, n)`       | 2    | Maximum over last N samples              | See §3.4                                    |
| `rolling_min(channel, n)`       | 2    | Minimum over last N samples              | See §3.4                                    |
| `lap_avg(channel)`              | 1    | Average over last completed lap          | See §3.5                                    |
| `lap_max(channel)`              | 1    | Max over last completed lap              | See §3.5                                    |
| `lap_min(channel)`              | 1    | Min over last completed lap              | See §3.5                                    |
| `lap_start(channel)`            | 1    | Value of channel at start of current lap | See §3.5                                    |
| `if(cond, true_val, false_val)` | 3    | Conditional (ternary)                    | Evaluate cond, return true_val or false_val |

### 2.4 — Stateful functions (history buffer)

`prev()`, `delta()`, `rate()`, `rolling_avg()`, `rolling_max()`, `rolling_min()` all require access to previous sample values. The engine needs a **history buffer** per channel.

**Implementation:**

```python
class ChannelHistory:
    """
    Ring buffer storing the last N samples for a channel.
    N should be large enough for the largest rolling window any formula uses.
    Default max: 500 samples (25 seconds at 20 Hz).
    """
    def __init__(self, max_size: int = 500):
        self.buffer = collections.deque(maxlen=max_size)

    def push(self, value: float) -> None:
        self.buffer.append(value)

    def prev(self, n: int = 1) -> float:
        """Value n samples ago. Returns 0.0 if not enough history."""
        if len(self.buffer) > n:
            return self.buffer[-(n + 1)]
        return 0.0

    def rolling_avg(self, n: int) -> float:
        samples = list(self.buffer)[-n:]
        return sum(samples) / len(samples) if samples else 0.0

    def rolling_max(self, n: int) -> float:
        samples = list(self.buffer)[-n:]
        return max(samples) if samples else 0.0

    def rolling_min(self, n: int) -> float:
        samples = list(self.buffer)[-n:]
        return min(samples) if samples else 0.0
```

**Important:** The history buffer stores values for BOTH raw channels and math channels. When a math channel references `prev(speed)`, it reads from speed's history. When it references `prev(my_custom_channel)`, it reads from that math channel's history. This means math channel outputs must also be pushed into the history buffer after each evaluation.

**`prev()` with channel name argument:**
Note that `prev(channel)` takes a channel NAME, not a value. The AST evaluator must detect when `prev`, `delta`, `rate`, `rolling_avg`, `rolling_max`, `rolling_min` are called and resolve the first argument as a channel name string (from the `ast.Name` node), NOT evaluate it as a value. This is a special case in the evaluator.

```python
# When evaluating ast.Call for prev/delta/rate/rolling_*:
# - First arg must be an ast.Name (channel name)
# - Look up that channel's history buffer
# - Do NOT evaluate the first arg as a value
```

### 2.5 — Lap-boundary functions

`lap_avg()`, `lap_max()`, `lap_min()`, `lap_start()` reference data from the last completed lap or the start of the current lap.

**Implementation:**

The engine needs to listen for the app's lap-complete event. When a lap completes:

1. For every raw channel AND every math channel, compute and cache:
   - `lap_avg`: mean of all samples during that lap
   - `lap_max`: max of all samples during that lap
   - `lap_min`: min of all samples during that lap
2. At lap start, snapshot the current value of every channel into `lap_start_values`

```python
class LapBoundaryCache:
    """Updated at each lap completion."""
    lap_avg_values: dict[str, float]    # channel_name → average over last lap
    lap_max_values: dict[str, float]
    lap_min_values: dict[str, float]
    lap_start_values: dict[str, float]  # channel_name → value at start of current lap

    # Also need to accumulate during the lap:
    lap_accumulators: dict[str, list[float]]  # channel_name → all samples this lap
```

`lap_avg()`, `lap_max()`, `lap_min()` return cached values from the LAST COMPLETED lap. Before the first lap completes, they return 0.0.

`lap_start()` returns the snapshot from the start of the CURRENT lap. Before the first lap starts, it returns the first sample received.

### 2.6 — Evaluation order

Math channels can reference other math channels. The engine must evaluate them in dependency order.

**On channel add/edit:** Build a dependency graph and compute a topological sort. If the sort fails (cycle detected), reject the channel with error `"Circular dependency: {channel_a} → {channel_b} → {channel_a}"`.

```python
def get_evaluation_order(channels: list[MathChannel]) -> list[str]:
    """
    Topological sort of math channels by dependency.
    Raw telemetry channels are leaf nodes (no dependencies).
    Raises CyclicDependencyError if a cycle is detected.
    """
    # Build adjacency list from each channel's dependencies
    # Kahn's algorithm or DFS-based topological sort
    # Return list of channel names in evaluation order
```

**At each tick:**

1. Push all raw channel values into their history buffers
2. Evaluate math channels in topological order
3. After evaluating each math channel, push its result into its history buffer
4. Return all math channel values as a dict

### 2.7 — Error handling

The engine must NEVER crash, throw an unhandled exception, or freeze the UI. Telemetry keeps flowing regardless of math channel errors.

| Error                                            | Behavior                                                        |
| ------------------------------------------------ | --------------------------------------------------------------- |
| Division by zero                                 | Return `0.0` for that channel this tick                         |
| `sqrt` of negative                               | Return `0.0`                                                    |
| NaN result                                       | Replace with `0.0`                                              |
| Inf / -Inf result                                | Clamp to `±1e9`                                                 |
| Unknown channel (stale reference after deletion) | Return `0.0`, log warning once                                  |
| History buffer empty (first few ticks)           | `prev()` returns `0.0`, rolling functions use available samples |
| Evaluation exceeds time budget                   | Skip remaining channels this tick, log warning                  |

**Performance budget:** All math channels combined must evaluate in < 5ms per tick. Measure with `time.perf_counter()`. If exceeded, log a warning with the channel that took longest. Do NOT skip ticks or drop telemetry — just skip the slow math channels for that tick.

---

## 3. Data Structures

```python
from dataclasses import dataclass, field
from typing import Optional
import ast

@dataclass
class MathChannel:
    name: str                           # snake_case, unique, no spaces
    formula: str                        # raw formula string as entered by user
    unit: str = ""                      # display unit label ("°C", "%", "km/h", "G", etc.)
    color: str = "#FFFFFF"              # hex color for graph plotting
    visible: bool = True                # whether shown on telemetry graphs
    built_in: bool = False              # True for pre-built channels (not editable, not deletable)
    description: str = ""               # short explanation shown in the channel list

    # Computed at parse time — not persisted
    compiled_ast: Optional[ast.AST] = field(default=None, repr=False)
    dependencies: list[str] = field(default_factory=list)  # channel names this formula references


class MathEngine:
    """
    Core engine. Parses, validates, and evaluates math channel formulas.
    Thread-safe for the telemetry tick loop.
    """

    def __init__(self):
        self.channels: dict[str, MathChannel] = {}          # name → MathChannel
        self.evaluation_order: list[str] = []                # topological sort result
        self.history: dict[str, ChannelHistory] = {}         # name → history buffer
        self.lap_cache: LapBoundaryCache = LapBoundaryCache()
        self._last_dt: float = 0.05                          # default 20 Hz
        self._last_tick_time: float = 0.0

    # --- Channel management ---
    def add_channel(self, name: str, formula: str, unit: str = "", color: str = "#FFFFFF",
                    built_in: bool = False, description: str = "") -> tuple[bool, str]:
        """
        Parse, validate, and register a new math channel.
        Returns (success: bool, error_message: str).
        Error message is empty on success.
        """
        ...

    def edit_channel(self, name: str, new_formula: str = None, new_unit: str = None,
                     new_color: str = None, new_visible: bool = None) -> tuple[bool, str]:
        """Edit an existing channel. Returns (success, error)."""
        ...

    def remove_channel(self, name: str) -> tuple[bool, str]:
        """
        Remove a channel. Fails if other channels depend on it.
        Returns (success, error).
        """
        ...

    def validate_formula(self, formula: str, exclude_name: str = None) -> tuple[bool, str, list[str]]:
        """
        Validate a formula without registering it.
        Returns (valid, error_message, list_of_dependencies).
        exclude_name: when editing a channel, exclude its own name from circular dependency check.
        """
        ...

    # --- Evaluation (called every telemetry tick) ---
    def evaluate(self, raw_channels: dict[str, float], timestamp: float) -> dict[str, float]:
        """
        Evaluate all math channels given current raw telemetry values.
        Returns dict of {channel_name: computed_value} for all math channels.

        1. Compute dt from timestamp
        2. Push raw values into history buffers
        3. Evaluate math channels in topological order
        4. Push math channel results into history buffers
        5. Return results
        """
        ...

    # --- Lap boundary events ---
    def on_lap_complete(self) -> None:
        """Called when a lap finishes. Finalizes lap_avg/max/min caches and resets accumulators."""
        ...

    def on_lap_start(self, raw_channels: dict[str, float]) -> None:
        """Called when a new lap begins. Snapshots lap_start values."""
        ...

    # --- Persistence ---
    def save_to_json(self, filepath: str) -> None:
        """Save all user-defined channels to JSON."""
        ...

    def load_from_json(self, filepath: str) -> None:
        """Load user-defined channels from JSON. Validates all formulas."""
        ...

    # --- Query ---
    def get_all_channels(self) -> list[MathChannel]:
        """Return all channels (built-in + user-defined) in evaluation order."""
        ...

    def get_available_names(self) -> list[str]:
        """Return all names that can be used in formulas (raw channels + math channels + constants)."""
        ...
```

---

## 4. Pre-Built Math Channels

Ship these by default. They are `built_in=True` — visible, viewable as learning references, duplicatable into editable copies, but not directly editable or deletable. Users can toggle their visibility.

### Tyre diagnostics

```
Name:           front_temp_avg
Formula:        avg(tyre_temp_fl_i, tyre_temp_fl_m, tyre_temp_fl_o, tyre_temp_fr_i, tyre_temp_fr_m, tyre_temp_fr_o)
Unit:           °C
Description:    Average front tyre temperature across both fronts
Color:          #FF6B35

Name:           rear_temp_avg
Formula:        avg(tyre_temp_rl_i, tyre_temp_rl_m, tyre_temp_rl_o, tyre_temp_rr_i, tyre_temp_rr_m, tyre_temp_rr_o)
Unit:           °C
Description:    Average rear tyre temperature across both rears
Color:          #4ECDC4

Name:           temp_balance_fb
Formula:        front_temp_avg - rear_temp_avg
Unit:           °C
Description:    Front vs rear tyre temp balance. Positive = fronts hotter.
Color:          #FFE66D

Name:           fl_temp_spread
Formula:        tyre_temp_fl_i - tyre_temp_fl_o
Unit:           °C
Description:    Front-left inner vs outer temp spread. High = too much camber or overloading.
Color:          #FF6B6B

Name:           fr_temp_spread
Formula:        tyre_temp_fr_i - tyre_temp_fr_o
Unit:           °C
Description:    Front-right inner vs outer temp spread.
Color:          #C44D58
```

### Driving technique

```
Name:           trail_brake_flag
Formula:        if(brake > 0.05 and abs(steering) > 0.1, 1, 0)
Unit:
Description:    1 when trail braking (brake + steering simultaneously), 0 otherwise.
Color:          #45B7D1

Name:           throttle_rate
Formula:        clamp(rate(throttle), -50, 50)
Unit:           /s
Description:    How fast you're applying or releasing throttle. Smooth = low values.
Color:          #96CEB4

Name:           brake_rate
Formula:        clamp(rate(brake), -50, 50)
Unit:           /s
Description:    How fast you're applying or releasing brake.
Color:          #D4776B

Name:           throttle_smoothness
Formula:        rolling_avg(abs(delta(throttle)), 20)
Unit:
Description:    Throttle smoothness score. Lower = smoother application. Watch this to improve car control.
Color:          #88D8B0
```

### Performance

```
Name:           accel_longitudinal
Formula:        rate(speed) / 3.6
Unit:           m/s²
Description:    Longitudinal acceleration (braking is negative, accelerating is positive).
Color:          #FFEAA7

Name:           peak_brake_recent
Formula:        rolling_max(brake, 100)
Unit:
Description:    Your peak brake pressure over the last 5 seconds. Are you using the full braking capability?
Color:          #DFE6E9

Name:           fuel_burn_rate
Formula:        if(lap_avg(speed) > 10, lap_start(fuel_remaining) - fuel_remaining, 0)
Unit:           L
Description:    Fuel used so far this lap. Resets each lap.
Color:          #FDCB6E
```

**Note on pre-built channels that depend on other pre-built channels:** `temp_balance_fb` depends on `front_temp_avg` and `rear_temp_avg`. The topological sort handles this — just make sure all three are registered and the sort will order them correctly.

**Note on sim-specific channels:** Some raw channels (tyre temps, brake temps) are only available in sim racing mode. Pre-built channels that reference unavailable channels should gracefully return `0.0` — the engine's unknown-channel fallback handles this. In the UI, these channels should be grayed out with a tooltip: "Not available in OBD-II mode."

---

## 5. UI: Math Channel Manager

### 5.1 — Entry point

A **calculator icon button** (🧮 or similar) in the **Telemetry tab toolbar**. Clicking it opens the Math Channel Manager as a **side panel** on the right side of the Telemetry tab (not a modal dialog — the user should be able to see the telemetry graphs updating while they work on formulas).

### 5.2 — Panel layout

The panel has three sections stacked vertically:

**Section 1: Channel list (scrollable, takes most of the space)**

Each channel is a row:

```
[✓] 🟠 throttle_smoothness          0.034 /s
    rolling_avg(abs(delta(throttle)), 20)
    [Edit] [Duplicate] [Delete]
```

- Checkbox: toggle visibility on graphs
- Color swatch: the channel's graph line color (clickable to change)
- Name: bold
- Live value: updating in real-time, right-aligned, with unit
- Formula: shown below the name in monospace, smaller font, gray text
- Action buttons: appear on hover or always visible
  - **Edit:** opens the formula editor with this channel's values
  - **Duplicate:** creates a copy with name `{original}_copy` and opens the editor
  - **Delete:** confirmation dialog, then removes (blocked if other channels depend on it)

Built-in channels show a 📌 icon instead of Delete, and Edit is replaced with **View** (read-only). Duplicate is still available.

**Separate the list into two groups:**

1. "Your Channels" — user-defined, at the top
2. "Built-in" — pre-built, collapsible section below

**Section 2: Add Channel button**

A prominent "+ Add Channel" button that opens the formula editor.

**Section 3: Status bar**

One line at the bottom: "12 channels active — eval time: 1.2ms / tick" showing real-time performance info.

### 5.3 — Formula editor

Opens inline within the panel (replaces the channel list temporarily) or as an expanding section. NOT a separate window.

**Fields:**

1. **Name** — text input, validated on keystroke:
   - Must be snake_case (lowercase letters, numbers, underscores only)
   - Must not conflict with raw channel names, function names, or constants
   - Must be unique among math channels
   - Max 40 characters
   - Show validation state: green border if valid, red border + error text if not

2. **Formula** — monospace text input, the main event:
   - **Syntax highlighting:** Color-code as the user types:
     - Channel names (raw + math): one color (e.g., cyan/teal)
     - Function names: another color (e.g., blue)
     - Numbers: another color (e.g., orange)
     - Operators: default text color
     - Unrecognized names: red underline
   - **Autocomplete dropdown:** Triggered on every keystroke when typing a name. Show a filtered list of:
     - Raw telemetry channel names (grouped under "Telemetry")
     - Math channel names (grouped under "Math Channels")
     - Function names (grouped under "Functions", show signature like `rolling_avg(channel, n)`)
     - Constants (`pi`, `e`, `dt`)
     - Pressing Tab or Enter selects the highlighted suggestion
     - Pressing Escape dismisses the dropdown
   - **Live validation:** On every keystroke (debounced ~200ms):
     - Parse the formula with `validate_formula()`
     - If valid: green checkmark icon, show dependency list below ("Uses: speed, brake, steering")
     - If invalid: red X icon, show error message below in red ("Unknown channel: 'speeed'. Did you mean 'speed'?")
   - **Multi-line support:** Allow line breaks for complex formulas. Evaluate as a single expression (strip newlines before parsing).

3. **Live preview** — below the formula field:
   - If the formula is valid, show the current computed value updating at ~2-4 Hz (don't need full 20 Hz in the editor, just enough to show it's alive)
   - Format: `Current value: 0.034 /s`
   - If the formula is invalid, show the error here instead

4. **Unit** — short text input, free-form. Suggested units shown as placeholder text: "°C, %, km/h, G, ..."

5. **Color** — color picker or a grid of pre-selected colors (8-12 options covering distinct hues). The selected color previews on a mini line segment.

6. **Description** — optional text input, one line. Shown in the channel list and as a tooltip on graphs.

7. **Buttons:**
   - **Save** — validates, registers the channel, returns to the channel list
   - **Cancel** — discards changes, returns to the channel list
   - Save is disabled while the formula is invalid

### 5.4 — Graph integration

Math channels must appear in the Telemetry graph's channel selector (the UI element where users choose which channels to plot). Add them in a separate group:

```
── Telemetry ──
  ✓ Speed
  ✓ Throttle
  ✓ Brake
    Steering
    RPM
── Math Channels ──
  ✓ throttle_smoothness
  ✓ trail_brake_flag
    front_temp_avg
    temp_balance_fb
```

When selected, they plot with their assigned color on the same graph axes. If the unit differs significantly from other plotted channels, consider a secondary Y-axis (e.g., speed in km/h on left axis, throttle_smoothness as a dimensionless number on right axis).

### 5.5 — Lap Comparison integration

In the Lap Comparison view, math channels should also be available for overlay. The math engine must be able to evaluate a formula against stored historical lap data (not just live data). This means:

1. When a lap completes, store all raw telemetry samples for that lap (this already happens in S1napse)
2. To compute a math channel for a historical lap, replay the telemetry through the engine tick by tick
3. Cache the result so it doesn't need to be recomputed every time the user opens Lap Comparison

---

## 6. Persistence

### 6.1 — File location

```
S1napse/
├── math_channels.json    # next to S1napsse.exe or test-listener.py
```

### 6.2 — File format

```json
{
  "version": 1,
  "channels": [
    {
      "name": "temp_balance_fb",
      "formula": "front_temp_avg - rear_temp_avg",
      "unit": "°C",
      "color": "#FFE66D",
      "visible": true,
      "built_in": false,
      "description": "Front vs rear tyre temp balance"
    }
  ]
}
```

- Built-in channels are NOT saved to this file — they're defined in code (`math_presets.py`) and always loaded
- Only user-defined channels are persisted
- Save on every add/edit/delete/visibility toggle (debounced ~500ms to avoid excessive writes)
- Load on app start, after built-in channels are registered
- If the file is missing or corrupt, start with only built-in channels (no crash, no error dialog — just log a warning)

### 6.3 — Migration

Include a `version` field. If the format changes in future versions, write a migration function that reads old formats and converts. For v1, no migration needed — just document the format.

---

## 7. Module Structure

```
S1napse/
├── coaching/
│   ├── math_engine.py          # MathChannel dataclass, MathEngine class, ChannelHistory, LapBoundaryCache
│   ├── math_parser.py          # AST parsing, validation, dependency extraction, safe evaluator
│   ├── math_presets.py         # Pre-built channel definitions (list of MathChannel instances)
│   └── math_functions.py       # Implementation of all built-in functions (abs, rolling_avg, etc.)
├── widgets/
│   ├── math_channel_panel.py   # PyQt6 side panel: channel list, add/edit/delete UI
│   └── math_formula_editor.py  # PyQt6 formula editor: syntax highlighting, autocomplete, live preview
```

### Module responsibilities:

**`math_parser.py`** — Pure logic, no PyQt6 imports. Takes a formula string, returns a parsed AST, a list of dependencies, or a validation error. Also contains the safe AST evaluator that walks the tree and computes a value given a context dict.

**`math_functions.py`** — Pure logic. Contains the implementations of all built-in functions. Each function is a plain Python function. Also contains the function registry (name → function mapping, argument count validation).

**`math_engine.py`** — Orchestrator. Manages channels, history buffers, lap boundary caches, topological sort, and the tick-by-tick evaluation loop. Calls into `math_parser.py` and `math_functions.py`.

**`math_presets.py`** — Just data. A list of `MathChannel` instances with `built_in=True`. Imported by `math_engine.py` on initialization.

**`math_channel_panel.py`** — PyQt6 widget. Displays the channel list, handles add/edit/delete interactions, owns the formula editor widget. Communicates with `MathEngine` through direct method calls (not signals — the engine is not a QObject).

**`math_formula_editor.py`** — PyQt6 widget. The formula input field with syntax highlighting (use `QSyntaxHighlighter`), autocomplete (use `QCompleter` or a custom popup), and live preview. Owned by `math_channel_panel.py`.

---

## 8. Integration Points

### 8.1 — Telemetry tick loop

In `test-listener.py`, there is a main loop or timer that receives telemetry data at each tick. At the end of this handler, after raw channel values are available:

```python
# In the existing telemetry tick handler:
raw_values = {
    "speed": current_speed,
    "throttle": current_throttle,
    "brake": current_brake,
    # ... all raw channels
}

# Add this:
math_results = self.math_engine.evaluate(raw_values, current_timestamp)

# math_results is now available to the graph system alongside raw_values
all_channels = {**raw_values, **math_results}
```

### 8.2 — Lap boundary events

Hook into the existing lap detection logic:

```python
# When a new lap starts:
self.math_engine.on_lap_start(raw_values)

# When a lap completes:
self.math_engine.on_lap_complete()
```

### 8.3 — Graph system

The existing graph system reads from a channel data source. Extend it to include math channel values from `math_results`. Math channels should appear in the channel selector with their name, unit, and color.

### 8.4 — Data export

When exporting telemetry data (CSV or any future format), include math channel values as additional columns. Label them clearly — prefix with `math_` or put them in a separate section:

```csv
distance_m, speed, throttle, brake, ..., math_trail_brake_flag, math_throttle_smoothness, ...
```

---

## 9. Implementation Order

Build and test in this exact sequence. Each step should be independently testable before moving to the next.

1. **`math_functions.py`** — implement all built-in functions as plain Python functions. Write unit tests for each.

2. **`math_parser.py`** — implement the AST parser and safe evaluator. Unit tests:
   - Simple arithmetic: `"speed * 2"` → correct result
   - Function calls: `"abs(steering)"` → correct result
   - Nested: `"max(abs(steering), 0.5)"` → correct result
   - Conditional: `"if(brake > 0.05, 1, 0)"` → correct result
   - Rejects unsafe input: `"__import__('os')"` → validation error
   - Rejects attribute access: `"speed.__class__"` → validation error
   - Rejects unknown functions: `"custom_func(speed)"` → validation error
   - Rejects unknown channels: `"speeed * 2"` → error with suggestion

3. **`math_engine.py`** — implement the engine with history buffers, topological sort, and tick evaluation. Unit tests:
   - Add channel, evaluate, get result
   - Chain two channels (A depends on B), verify evaluation order
   - Circular dependency detection
   - `prev()` returns 0.0 on first tick, correct value on subsequent ticks
   - `rolling_avg()` with partial history (fewer samples than window)
   - Division by zero returns 0.0
   - Performance: 20 channels evaluate in < 5ms

4. **`math_presets.py`** — define all pre-built channels. Verify they all parse and validate without errors.

5. **Persistence** — implement save/load in `math_engine.py`. Test round-trip: save → load → verify all channels intact.

6. **Integration with telemetry loop** — hook `evaluate()` into the tick handler, hook lap events. Verify math channels update live.

7. **`math_formula_editor.py`** — build the PyQt6 formula editor with syntax highlighting and autocomplete.

8. **`math_channel_panel.py`** — build the full side panel UI.

9. **Graph integration** — add math channels to the graph channel selector and plotting system.

10. **Lap Comparison integration** — enable math channels in Lap Comparison by replaying historical lap data through the engine.

11. **Export integration** — include math channels in CSV and any future export formats.

---

## 10. Testing

### 10.1 — Unit tests

**`test_math_parser.py`:**

- Arithmetic evaluation correctness (10+ cases covering all operators)
- Function evaluation correctness (every built-in function)
- Operator precedence: `"2 + 3 * 4"` → 14, not 20
- Nested functions: `"avg(max(a, b), min(c, d))"` → correct
- Boolean logic: `"if(speed > 100 and brake > 0.5, 1, 0)"` → correct
- Security: rejects imports, attribute access, subscripts, assignments, lambdas, walrus operator, f-strings, starred expressions
- Error messages: unknown channel shows "Did you mean X?" if close match exists (Levenshtein distance ≤ 2)

**`test_math_engine.py`:**

- Single channel add/evaluate/remove lifecycle
- Multiple channels with dependencies: correct topological order
- Circular dependency: A→B→C→A → error
- Self-reference: A references A → error
- `prev(channel)` correctness after N ticks
- `rolling_avg()` correctness against manual calculation
- `delta()` and `rate()` correctness with known dt
- `lap_start()` and `lap_avg()` correctness across lap boundaries
- Remove channel that others depend on → error with message listing dependents
- Performance benchmark: 20 channels, 10000 ticks, all within time budget

**`test_math_presets.py`:**

- All pre-built channels parse without errors
- All pre-built channel dependencies resolve (no missing channel references)
- No circular dependencies among pre-built channels

### 10.2 — Edge cases

- First tick ever (no history) — all `prev()`/`rolling_*()` return 0.0, no crash
- Channel references a raw channel that doesn't exist yet (sim hasn't started) — returns 0.0
- User deletes a channel that a pre-built channel depends on — block deletion, show error
- User creates a channel with the same name as a raw channel — validation rejects it
- Formula is empty string — validation error "Formula cannot be empty"
- Formula is just a number `"42"` — valid, returns 42.0 every tick (constant channel)
- Formula is just a channel name `"speed"` — valid, mirrors that channel (alias)
- Very long formula (1000+ characters) — should still parse, but warn if evaluation is slow
- 100+ math channels — should still work, warn if approaching time budget
- App closes mid-evaluation — no crash, no corrupt save file (use atomic write: write to temp file, then rename)

---

## 11. Available Raw Telemetry Channels

These are the raw channel names available from the telemetry layer. Use these exact names as variables in formulas. Update this list if the actual variable names differ.

### Sim Racing (20 Hz)

| Channel Name     | Type  | Range       | Notes                          |
| ---------------- | ----- | ----------- | ------------------------------ |
| `speed`          | float | 0-350+ km/h | Ground speed                   |
| `rpm`            | int   | 0-15000     | Engine RPM                     |
| `gear`           | int   | -1 to 8     | -1=reverse, 0=neutral          |
| `throttle`       | float | 0.0-1.0     | Throttle position              |
| `brake`          | float | 0.0-1.0     | Brake pressure                 |
| `steering`       | float | -1.0 to 1.0 | Steering angle (negative=left) |
| `tyre_temp_fl_i` | float | °C          | Front-left inner               |
| `tyre_temp_fl_m` | float | °C          | Front-left middle              |
| `tyre_temp_fl_o` | float | °C          | Front-left outer               |
| `tyre_temp_fr_i` | float | °C          | Front-right inner              |
| `tyre_temp_fr_m` | float | °C          | Front-right middle             |
| `tyre_temp_fr_o` | float | °C          | Front-right outer              |
| `tyre_temp_rl_i` | float | °C          | Rear-left inner                |
| `tyre_temp_rl_m` | float | °C          | Rear-left middle               |
| `tyre_temp_rl_o` | float | °C          | Rear-left outer                |
| `tyre_temp_rr_i` | float | °C          | Rear-right inner               |
| `tyre_temp_rr_m` | float | °C          | Rear-right middle              |
| `tyre_temp_rr_o` | float | °C          | Rear-right outer               |
| `tyre_press_fl`  | float | PSI         | Front-left pressure            |
| `tyre_press_fr`  | float | PSI         | Front-right pressure           |
| `tyre_press_rl`  | float | PSI         | Rear-left pressure             |
| `tyre_press_rr`  | float | PSI         | Rear-right pressure            |
| `brake_temp_fl`  | float | °C          | Front-left brake disc          |
| `brake_temp_fr`  | float | °C          | Front-right brake disc         |
| `brake_temp_rl`  | float | °C          | Rear-left brake disc           |
| `brake_temp_rr`  | float | °C          | Rear-right brake disc          |
| `fuel_remaining` | float | liters      | Fuel in tank                   |
| `lap_time`       | float | seconds     | Current lap elapsed            |
| `distance`       | float | meters      | Distance this lap              |
| `car_x`          | float | meters      | World X position               |
| `car_z`          | float | meters      | World Z position               |
| `abs_active`     | bool  | 0/1         | ABS intervening                |
| `tc_active`      | bool  | 0/1         | TC intervening                 |
| `delta_to_best`  | float | seconds     | Delta vs reference             |

### OBD-II (2-4 Hz)

| Channel Name   | Type  | Notes                  |
| -------------- | ----- | ---------------------- |
| `speed`        | float | Vehicle speed          |
| `rpm`          | int   | Engine RPM             |
| `throttle`     | float | Throttle position      |
| `coolant_temp` | float | Coolant temperature    |
| `intake_temp`  | float | Intake air temperature |
| `fuel_level`   | float | Fuel level %           |

---

## 12. Final Checklist

Before considering this feature complete:

**Engine:**

- [ ] AST parser rejects all unsafe input (no eval, no imports, no attribute access, no subscripts)
- [ ] All 17 built-in functions work correctly with unit tests
- [ ] Circular dependency detection catches direct and indirect cycles
- [ ] Division by zero returns 0.0 without crashing
- [ ] NaN / Inf values are clamped and don't propagate
- [ ] `prev()` and `rolling_*()` handle empty/partial history gracefully
- [ ] Topological sort produces correct evaluation order
- [ ] All math channels combined evaluate in < 5ms per tick (measured)
- [ ] Lap boundary functions (`lap_avg`, `lap_start`, etc.) update correctly at lap transitions

**Pre-built channels:**

- [ ] All pre-built channels parse, validate, and evaluate without errors
- [ ] Pre-built channels that reference sim-only data return 0.0 in OBD-II mode without crashing
- [ ] Pre-built channels are visible but not editable or deletable
- [ ] Duplicate creates an editable copy

**UI:**

- [ ] Formula editor has working syntax highlighting
- [ ] Autocomplete shows channel names and functions, selectable with Tab/Enter
- [ ] Live preview updates while typing (debounced)
- [ ] Validation errors are shown inline in real-time with helpful messages
- [ ] Channel list shows live values updating
- [ ] Color picker works
- [ ] Delete is blocked when other channels depend on the target (error shows dependents)
- [ ] Side panel doesn't block or slow down the main telemetry view

**Integration:**

- [ ] Math channels appear in Telemetry graph channel selector
- [ ] Math channels plot correctly with assigned colors
- [ ] Math channels appear in Lap Comparison
- [ ] Math channels are included in data exports
- [ ] User-defined channels persist across sessions (math_channels.json)
- [ ] Corrupt or missing JSON file doesn't crash the app

**Performance:**

- [ ] 20 active math channels don't cause any visible UI lag
- [ ] History buffers don't grow unbounded (ring buffer with max size)
- [ ] JSON save is debounced and uses atomic write
